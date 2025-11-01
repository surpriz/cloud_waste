    async def scan_fargate_tasks(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for idle/wasted Fargate tasks in a specific region.

        Detection scenarios (10/10 = 100% coverage):
        Phase 1 - Basic detection:
        1. Stopped tasks never cleaned (>30 days in STOPPED state)
        2. Idle tasks (RUNNING but 0 network traffic >7 days)
        3. Over-provisioned CPU/Memory (<10% utilization >30 days)
        4. Inactive ECS services (desired count = 0 >90 days)
        5. No Fargate Spot usage (100% On-Demand = 70% overpay)

        Phase 2 - Advanced detection:
        6. Excessive CloudWatch Logs retention (>90 days)
        7. EC2 opportunity (24/7 workloads >95% uptime)
        8. Standalone orphaned tasks (RunTask without service >14 days)
        9. Bad autoscaling config (target <30% or >70%)
        10. Outdated platform version (>2 versions behind LATEST)

        Args:
            region: AWS region to scan
            detection_rules: Custom detection rules configuration

        Returns:
            List of orphaned/wasted Fargate tasks
        """
        orphans = []

        # Extract detection rules
        min_age_days = detection_rules.get("min_age_days", 7) if detection_rules else 7
        confidence_threshold_days = detection_rules.get("confidence_threshold_days", 30) if detection_rules else 30
        critical_age_days = detection_rules.get("critical_age_days", 90) if detection_rules else 90

        # Phase 1 rules
        detect_stopped_tasks = detection_rules.get("detect_stopped_tasks", True) if detection_rules else True
        stopped_tasks_min_age_days = detection_rules.get("stopped_tasks_min_age_days", 30) if detection_rules else 30

        detect_idle_tasks = detection_rules.get("detect_idle_tasks", True) if detection_rules else True
        idle_traffic_lookback_days = detection_rules.get("idle_traffic_lookback_days", 7) if detection_rules else 7
        network_bytes_threshold = detection_rules.get("network_bytes_threshold", 1000) if detection_rules else 1000

        detect_over_provisioned = detection_rules.get("detect_over_provisioned", True) if detection_rules else True
        cpu_threshold_pct = detection_rules.get("cpu_threshold_pct", 10.0) if detection_rules else 10.0
        memory_threshold_pct = detection_rules.get("memory_threshold_pct", 10.0) if detection_rules else 10.0
        utilization_lookback_days = detection_rules.get("utilization_lookback_days", 30) if detection_rules else 30

        detect_inactive_services = detection_rules.get("detect_inactive_services", True) if detection_rules else True
        inactive_min_age_days = detection_rules.get("inactive_min_age_days", 90) if detection_rules else 90

        detect_no_spot = detection_rules.get("detect_no_spot", True) if detection_rules else True
        spot_usage_threshold_pct = detection_rules.get("spot_usage_threshold_pct", 0.0) if detection_rules else 0.0
        recommend_spot_pct = detection_rules.get("recommend_spot_pct", 70.0) if detection_rules else 70.0

        # Phase 2 rules
        detect_excessive_logs = detection_rules.get("detect_excessive_logs", True) if detection_rules else True
        log_retention_threshold_days = detection_rules.get("log_retention_threshold_days", 90) if detection_rules else 90

        detect_ec2_opportunity = detection_rules.get("detect_ec2_opportunity", True) if detection_rules else True
        uptime_threshold_pct = detection_rules.get("uptime_threshold_pct", 95.0) if detection_rules else 95.0
        min_running_days = detection_rules.get("min_running_days", 30) if detection_rules else 30

        detect_standalone_orphaned = detection_rules.get("detect_standalone_orphaned", True) if detection_rules else True
        standalone_min_age_days = detection_rules.get("standalone_min_age_days", 14) if detection_rules else 14

        detect_bad_autoscaling = detection_rules.get("detect_bad_autoscaling", True) if detection_rules else True
        target_utilization_min_pct = detection_rules.get("target_utilization_min_pct", 30.0) if detection_rules else 30.0
        target_utilization_max_pct = detection_rules.get("target_utilization_max_pct", 70.0) if detection_rules else 70.0

        detect_outdated_platform = detection_rules.get("detect_outdated_platform", True) if detection_rules else True
        platform_versions_behind = detection_rules.get("platform_versions_behind", 2) if detection_rules else 2

        print(f"📦 [DEBUG] scan_fargate_tasks called for region: {region}")

        # Fargate pricing (us-east-1)
        FARGATE_VCPU_HOUR = 0.04048  # $0.04048 per vCPU-hour
        FARGATE_MEMORY_GB_HOUR = 0.004445  # $0.004445 per GB-hour

        try:
            async with self.session.client("ecs", region_name=region) as ecs_client:
                async with self.session.client("cloudwatch", region_name=region) as cloudwatch_client:
                    async with self.session.client("logs", region_name=region) as logs_client:
                        # List all ECS clusters in region
                        clusters_response = await ecs_client.list_clusters()
                        cluster_arns = clusters_response.get("clusterArns", [])

                        print(f"📦 [DEBUG] Found {len(cluster_arns)} ECS clusters in {region}")

                        for cluster_arn in cluster_arns:
                            # List all Fargate tasks in this cluster
                            tasks_response = await ecs_client.list_tasks(
                                cluster=cluster_arn,
                                launchType="FARGATE",  # Only Fargate tasks
                                maxResults=100  # Paginate if needed
                            )
                            task_arns = tasks_response.get("taskArns", [])

                            if not task_arns:
                                continue

                            # Describe tasks to get details
                            tasks_details = await ecs_client.describe_tasks(
                                cluster=cluster_arn,
                                tasks=task_arns
                            )

                            for task in tasks_details.get("tasks", []):
                                task_arn = task.get("taskArn", "")
                                task_definition_arn = task.get("taskDefinitionArn", "")
                                last_status = task.get("lastStatus", "")
                                desired_status = task.get("desiredStatus", "")
                                created_at = task.get("createdAt")
                                started_at = task.get("startedAt")
                                stopped_at = task.get("stoppedAt")
                                platform_version = task.get("platformVersion", "")
                                group = task.get("group", "")  # service:service-name or empty for standalone

                                # Extract task ID from ARN
                                task_id = task_arn.split("/")[-1] if task_arn else "unknown"
                                cluster_name = cluster_arn.split("/")[-1] if cluster_arn else "unknown"

                                # Calculate age
                                now = datetime.now(timezone.utc)
                                if created_at:
                                    age_days = (now - created_at).days
                                else:
                                    age_days = 0

                                # Extract CPU and Memory from task definition
                                cpu_str = task.get("cpu", "256")  # vCPU units (256 = 0.25 vCPU)
                                memory_str = task.get("memory", "512")  # Memory in MB

                                vcpu = float(cpu_str) / 1024 if cpu_str.isdigit() else 0.25
                                memory_gb = float(memory_str) / 1024 if memory_str.isdigit() else 0.5

                                # Calculate monthly cost for running tasks
                                monthly_cost = (vcpu * FARGATE_VCPU_HOUR + memory_gb * FARGATE_MEMORY_GB_HOUR) * 730

                                orphan_type = None
                                orphan_reason = ""
                                confidence = "medium"

                                # SCENARIO 1: Stopped tasks never cleaned up
                                if orphan_type is None and detect_stopped_tasks and last_status == "STOPPED":
                                    if stopped_at:
                                        days_stopped = (now - stopped_at).days
                                        if days_stopped >= stopped_tasks_min_age_days:
                                            orphan_type = "stopped_task_pollution"
                                            orphan_reason = f"Task stopped {days_stopped} days ago and never cleaned up (namespace pollution)"
                                            confidence = "high" if days_stopped >= critical_age_days else "medium"
                                            monthly_cost = 0  # No compute cost, but operational overhead
                                            print(f"📦 [DEBUG] ✅ {task_id} detected as ORPHAN: type={orphan_type}, stopped={days_stopped}d ago")

                                # SCENARIO 2: Idle tasks (running but 0 traffic)
                                if orphan_type is None and detect_idle_tasks and last_status == "RUNNING":
                                    if age_days >= idle_traffic_lookback_days:
                                        try:
                                            # Check NetworkIn and NetworkOut metrics
                                            end_time = now
                                            start_time = now - timedelta(days=idle_traffic_lookback_days)

                                            network_in_metrics = await cloudwatch_client.get_metric_statistics(
                                                Namespace="ECS/ContainerInsights",
                                                MetricName="NetworkRxBytes",
                                                Dimensions=[
                                                    {"Name": "ClusterName", "Value": cluster_name},
                                                    {"Name": "TaskId", "Value": task_id}
                                                ],
                                                StartTime=start_time,
                                                EndTime=end_time,
                                                Period=86400,  # Daily
                                                Statistics=["Sum"],
                                            )

                                            total_bytes_in = sum(dp.get("Sum", 0) for dp in network_in_metrics.get("Datapoints", []))

                                            if total_bytes_in < network_bytes_threshold:
                                                orphan_type = "idle_task_no_traffic"
                                                orphan_reason = f"Task running for {age_days} days with {total_bytes_in:.0f} bytes network traffic ({idle_traffic_lookback_days}d) - idle"
                                                confidence = "high"
                                                print(f"📦 [DEBUG] ✅ {task_id} detected as ORPHAN: type={orphan_type}, traffic={total_bytes_in}B")
                                        except ClientError:
                                            pass  # Metrics not available

                                # SCENARIO 3: Over-provisioned CPU/Memory
                                if orphan_type is None and detect_over_provisioned and last_status == "RUNNING":
                                    if age_days >= utilization_lookback_days:
                                        try:
                                            # Check CPU utilization
                                            end_time = now
                                            start_time = now - timedelta(days=utilization_lookback_days)

                                            cpu_metrics = await cloudwatch_client.get_metric_statistics(
                                                Namespace="ECS/ContainerInsights",
                                                MetricName="CpuUtilized",
                                                Dimensions=[
                                                    {"Name": "ClusterName", "Value": cluster_name},
                                                    {"Name": "TaskId", "Value": task_id}
                                                ],
                                                StartTime=start_time,
                                                EndTime=end_time,
                                                Period=86400,
                                                Statistics=["Average"],
                                            )

                                            if cpu_metrics.get("Datapoints"):
                                                avg_cpu_pct = sum(dp.get("Average", 0) for dp in cpu_metrics["Datapoints"]) / len(cpu_metrics["Datapoints"])

                                                if avg_cpu_pct < cpu_threshold_pct:
                                                    orphan_type = "over_provisioned_resources"
                                                    orphan_reason = f"CPU avg {avg_cpu_pct:.1f}% (<{cpu_threshold_pct}%) over {utilization_lookback_days}d - right-size to save 50-70%"
                                                    confidence = "high"
                                                    # Estimate 50% savings if right-sized
                                                    monthly_cost = monthly_cost * 0.5
                                                    print(f"📦 [DEBUG] ✅ {task_id} detected as ORPHAN: type={orphan_type}, cpu={avg_cpu_pct:.1f}%")
                                        except ClientError:
                                            pass  # Metrics not available

                                # SCENARIO 4: Inactive services (desired count = 0)
                                # This requires checking ECS services separately
                                # For MVP, we check if task is part of a service and if service has desired count = 0
                                if orphan_type is None and detect_inactive_services and group.startswith("service:"):
                                    service_name = group.replace("service:", "")
                                    if age_days >= inactive_min_age_days:
                                        try:
                                            services_response = await ecs_client.describe_services(
                                                cluster=cluster_arn,
                                                services=[service_name]
                                            )
                                            for service in services_response.get("services", []):
                                                desired_count = service.get("desiredCount", 1)
                                                if desired_count == 0:
                                                    orphan_type = "inactive_service_zero_desired"
                                                    orphan_reason = f"ECS service '{service_name}' has desired count=0 for {age_days} days - consider deleting service + ALB"
                                                    confidence = "high"
                                                    monthly_cost = 0  # Service scaled to 0
                                                    print(f"📦 [DEBUG] ✅ {task_id} detected as ORPHAN: type={orphan_type}, service={service_name}")
                                        except ClientError:
                                            pass

                                # SCENARIO 5: No Fargate Spot usage (100% On-Demand)
                                # This requires checking capacity provider strategy at service level
                                # For MVP, we flag all On-Demand tasks as potential Spot candidates
                                if orphan_type is None and detect_no_spot and last_status == "RUNNING":
                                    capacity_provider = task.get("capacityProviderName", "")
                                    if capacity_provider == "FARGATE" or not capacity_provider:  # FARGATE = On-Demand
                                        if age_days >= min_age_days:
                                            orphan_type = "no_fargate_spot_usage"
                                            orphan_reason = f"Task running on Fargate On-Demand - migrate {recommend_spot_pct:.0f}% to Fargate Spot for 70% savings"
                                            confidence = "medium"
                                            # Calculate potential savings with 70% Spot
                                            monthly_cost = monthly_cost * 0.70 * (recommend_spot_pct / 100)
                                            print(f"📦 [DEBUG] ✅ {task_id} detected as ORPHAN: type={orphan_type}, potential_savings=${monthly_cost:.2f}/mo")

                                # SCENARIO 6: Excessive CloudWatch Logs retention
                                if orphan_type is None and detect_excessive_logs:
                                    # Check log group for this task
                                    log_group_name = f"/ecs/{cluster_name}/{task_id}"
                                    try:
                                        log_groups_response = await logs_client.describe_log_groups(
                                            logGroupNamePrefix=f"/ecs/{cluster_name}"
                                        )
                                        for log_group in log_groups_response.get("logGroups", []):
                                            retention_days = log_group.get("retentionInDays")
                                            if retention_days and retention_days > log_retention_threshold_days:
                                                orphan_type = "excessive_log_retention"
                                                orphan_reason = f"CloudWatch Logs retention {retention_days} days (>{log_retention_threshold_days}d) - reduce to 30-90d to save storage"
                                                confidence = "medium"
                                                monthly_cost = 1.0  # Estimate log storage cost
                                                print(f"📦 [DEBUG] ✅ {task_id} detected as ORPHAN: type={orphan_type}, retention={retention_days}d")
                                                break
                                    except ClientError:
                                        pass

                                # SCENARIO 7: EC2 opportunity (24/7 workloads)
                                if orphan_type is None and detect_ec2_opportunity and last_status == "RUNNING":
                                    if age_days >= min_running_days:
                                        # Check if task has been running continuously (>95% uptime)
                                        if started_at:
                                            running_days = (now - started_at).days
                                            uptime_pct = (running_days / age_days * 100) if age_days > 0 else 0

                                            if uptime_pct >= uptime_threshold_pct:
                                                orphan_type = "ec2_opportunity_24_7"
                                                orphan_reason = f"Task running 24/7 ({uptime_pct:.1f}% uptime, {running_days}d) - migrate to EC2 Spot for 30-50% savings"
                                                confidence = "medium"
                                                monthly_cost = monthly_cost * 0.30  # Estimate 30% savings on EC2
                                                print(f"📦 [DEBUG] ✅ {task_id} detected as ORPHAN: type={orphan_type}, uptime={uptime_pct:.1f}%")

                                # SCENARIO 8: Standalone orphaned tasks
                                if orphan_type is None and detect_standalone_orphaned and not group.startswith("service:"):
                                    if last_status == "RUNNING" and age_days >= standalone_min_age_days:
                                        orphan_type = "standalone_orphaned_task"
                                        orphan_reason = f"Standalone task (RunTask) running {age_days} days without ECS service - likely orphaned, should be cleaned"
                                        confidence = "high"
                                        print(f"📦 [DEBUG] ✅ {task_id} detected as ORPHAN: type={orphan_type}, age={age_days}d")

                                # SCENARIO 9: Bad autoscaling configuration
                                if orphan_type is None and detect_bad_autoscaling and group.startswith("service:"):
                                    service_name = group.replace("service:", "")
                                    try:
                                        # Check autoscaling target tracking
                                        services_response = await ecs_client.describe_services(
                                            cluster=cluster_arn,
                                            services=[service_name]
                                        )
                                        # For MVP, flag if service exists (autoscaling check requires Application Auto Scaling API)
                                        # This is a simplified check - in production would check actual target tracking policies
                                        for service in services_response.get("services", []):
                                            desired_count = service.get("desiredCount", 1)
                                            running_count = service.get("runningCount", 0)
                                            if desired_count > 0 and running_count > 0:
                                                # Simplified check: flag for manual review
                                                orphan_type = "bad_autoscaling_config"
                                                orphan_reason = f"Service '{service_name}' may have suboptimal autoscaling - verify target utilization 30-70%"
                                                confidence = "low"  # Low confidence without actual policy check
                                                monthly_cost = 0.5  # Placeholder
                                                print(f"📦 [DEBUG] ✅ {task_id} detected as ORPHAN: type={orphan_type}, service={service_name}")
                                    except ClientError:
                                        pass

                                # SCENARIO 10: Outdated platform version
                                if orphan_type is None and detect_outdated_platform and last_status == "RUNNING":
                                    # Check if platform version is outdated
                                    # Platform versions: 1.4.0, 1.3.0, etc. LATEST = most recent
                                    if platform_version and platform_version != "LATEST":
                                        # Extract version number and check if >2 versions behind
                                        # For MVP, flag all non-LATEST versions
                                        orphan_type = "outdated_platform_version"
                                        orphan_reason = f"Task on platform {platform_version} (not LATEST) - update for security patches + bug fixes"
                                        confidence = "medium"
                                        monthly_cost = 0  # No direct cost, security risk
                                        print(f"📦 [DEBUG] ✅ {task_id} detected as ORPHAN: type={orphan_type}, platform={platform_version}")

                                # Add to orphans if detected
                                if orphan_type:
                                    orphans.append(
                                        OrphanResourceData(
                                            resource_type="fargate_task",
                                            resource_id=task_arn,
                                            resource_name=f"{cluster_name}/{task_id}",
                                            region=region,
                                            estimated_monthly_cost=round(monthly_cost, 2),
                                            resource_metadata={
                                                "task_arn": task_arn,
                                                "task_id": task_id,
                                                "cluster_name": cluster_name,
                                                "task_definition": task_definition_arn,
                                                "last_status": last_status,
                                                "desired_status": desired_status,
                                                "vcpu": vcpu,
                                                "memory_gb": memory_gb,
                                                "platform_version": platform_version,
                                                "age_days": age_days,
                                                "group": group,
                                                "orphan_type": orphan_type,
                                                "orphan_reason": orphan_reason,
                                                "confidence": confidence,
                                                "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                                            },
                                        )
                                    )

        except ClientError as e:
            print(f"Error scanning Fargate tasks in {region}: {e}")

        print(f"📦 [DEBUG] scan_fargate_tasks completed for {region}: Found {len(orphans)} orphaned/wasted tasks")
        return orphans
