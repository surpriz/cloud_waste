"""Email service for sending verification and welcome emails."""

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import structlog

from app.core.config import settings

logger = structlog.get_logger()


def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None,
) -> bool:
    """
    Send an email using SMTP.

    Args:
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML content of the email
        text_content: Plain text fallback content

    Returns:
        True if email sent successfully, False otherwise
    """
    # Check if SMTP is configured
    if not settings.SMTP_HOST or not settings.EMAILS_FROM_EMAIL:
        logger.warning(
            "email.not_configured",
            reason="SMTP not configured, email not sent",
            to_email=to_email,
        )
        return False

    try:
        # Create message
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        # Add plain text part if provided
        if text_content:
            part1 = MIMEText(text_content, "plain")
            msg.attach(part1)

        # Add HTML part
        part2 = MIMEText(html_content, "html")
        msg.attach(part2)

        # Send email with SSL/TLS
        context = ssl.create_default_context()

        # Use SMTP_SSL (port 465) if port is 465, otherwise use SMTP with STARTTLS (port 587)
        if settings.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=context, timeout=30) as server:
                server.set_debuglevel(0)  # Set to 1 for debugging
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.EMAILS_FROM_EMAIL, to_email, msg.as_string())
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
                server.set_debuglevel(0)  # Set to 1 for debugging
                server.starttls(context=context)
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.EMAILS_FROM_EMAIL, to_email, msg.as_string())

        logger.info(
            "email.sent",
            to_email=to_email,
            subject=subject,
        )
        return True

    except Exception as e:
        logger.error(
            "email.send_failed",
            to_email=to_email,
            subject=subject,
            error=str(e),
        )
        return False


def get_verification_email_html(full_name: str, verification_url: str) -> str:
    """
    Get HTML template for email verification.

    Args:
        full_name: User's full name
        verification_url: URL for email verification

    Returns:
        HTML email content
    """
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Verify your email - CutCosts</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #f3f4f6;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table width="600" border="0" cellspacing="0" cellpadding="0" style="background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 20px; text-align: center;">
                            <h1 style="margin: 0; color: #1f2937; font-size: 28px; font-weight: 700;">
                                🛡️ CutCosts
                            </h1>
                            <p style="margin: 10px 0 0; color: #6b7280; font-size: 14px;">
                                Cloud Cost Optimization
                            </p>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 20px 40px;">
                            <h2 style="margin: 0 0 20px; color: #1f2937; font-size: 22px; font-weight: 600;">
                                Welcome {full_name}! 👋
                            </h2>
                            <p style="margin: 0 0 15px; color: #374151; font-size: 16px; line-height: 1.6;">
                                Thank you for signing up for <strong>CutCosts</strong>. To start optimizing your cloud costs, please confirm your email address by clicking the button below:
                            </p>

                            <!-- CTA Button -->
                            <table width="100%" border="0" cellspacing="0" cellpadding="0" style="margin: 30px 0;">
                                <tr>
                                    <td align="center">
                                        <a href="{verification_url}" style="display: inline-block; padding: 14px 32px; background-color: #2563eb; color: #ffffff; text-decoration: none; border-radius: 6px; font-size: 16px; font-weight: 600;">
                                            ✉️ Verify my email
                                        </a>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 20px 0 10px; color: #6b7280; font-size: 14px; line-height: 1.6;">
                                Or copy this link in your browser:
                            </p>
                            <p style="margin: 0; color: #2563eb; font-size: 13px; word-break: break-all;">
                                {verification_url}
                            </p>

                            <!-- Expiration notice -->
                            <div style="margin: 30px 0; padding: 16px; background-color: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 4px;">
                                <p style="margin: 0; color: #92400e; font-size: 14px;">
                                    ⏱️ <strong>This link expires in 7 days.</strong><br>
                                    After this period, your account will be automatically deleted.
                                </p>
                            </div>

                            <p style="margin: 20px 0 0; color: #6b7280; font-size: 14px; line-height: 1.6;">
                                If you didn't create a CutCosts account, you can ignore this email.
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 30px 40px; background-color: #f9fafb; border-top: 1px solid #e5e7eb; border-radius: 0 0 8px 8px;">
                            <p style="margin: 0; color: #9ca3af; font-size: 12px; text-align: center; line-height: 1.5;">
                                This email was sent by <strong>CutCosts</strong><br>
                                © 2025 CutCosts. All rights reserved.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def get_verification_email_text(full_name: str, verification_url: str) -> str:
    """
    Get plain text version for email verification.

    Args:
        full_name: User's full name
        verification_url: URL for email verification

    Returns:
        Plain text email content
    """
    return f"""
Welcome {full_name}!

Thank you for signing up for CutCosts. To start optimizing your cloud costs, please confirm your email address by clicking the link below:

{verification_url}

⏱️ This link expires in 7 days. After this period, your account will be automatically deleted.

If you didn't create a CutCosts account, you can ignore this email.

---
This email was sent by CutCosts
© 2025 CutCosts. All rights reserved.
"""


def send_verification_email(
    email: str,
    full_name: str,
    verification_token: str,
) -> bool:
    """
    Send email verification to user.

    Args:
        email: User email address
        full_name: User's full name
        verification_token: Verification token

    Returns:
        True if email sent successfully, False otherwise
    """
    verification_url = f"{settings.FRONTEND_URL}/auth/verify-email/{verification_token}"

    html_content = get_verification_email_html(full_name, verification_url)
    text_content = get_verification_email_text(full_name, verification_url)

    return send_email(
        to_email=email,
        subject="Verify your email - CutCosts",
        html_content=html_content,
        text_content=text_content,
    )


def get_welcome_email_html(full_name: str) -> str:
    """
    Get HTML template for welcome email.

    Args:
        full_name: User's full name

    Returns:
        HTML email content
    """
    app_url = settings.FRONTEND_URL

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to CutCosts</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #f3f4f6;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table width="600" border="0" cellspacing="0" cellpadding="0" style="background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 20px; text-align: center;">
                            <h1 style="margin: 0; color: #1f2937; font-size: 32px; font-weight: 700;">
                                🎉 Congratulations!
                            </h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 20px 40px;">
                            <h2 style="margin: 0 0 20px; color: #1f2937; font-size: 22px; font-weight: 600;">
                                Your account is activated, {full_name}!
                            </h2>
                            <p style="margin: 0 0 15px; color: #374151; font-size: 16px; line-height: 1.6;">
                                Your email address has been verified successfully. You can now access all <strong>CutCosts</strong> features:
                            </p>

                            <!-- Features list -->
                            <table width="100%" border="0" cellspacing="0" cellpadding="0" style="margin: 25px 0;">
                                <tr>
                                    <td style="padding: 12px 0;">
                                        <span style="font-size: 24px;">📊</span>
                                        <strong style="color: #1f2937; font-size: 15px; margin-left: 10px;">Automated scans</strong>
                                        <p style="margin: 5px 0 0 44px; color: #6b7280; font-size: 14px;">Detection of orphaned AWS and Azure resources</p>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 12px 0;">
                                        <span style="font-size: 24px;">💰</span>
                                        <strong style="color: #1f2937; font-size: 15px; margin-left: 10px;">Identified savings</strong>
                                        <p style="margin: 5px 0 0 44px; color: #6b7280; font-size: 14px;">Accurate waste cost estimation</p>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 12px 0;">
                                        <span style="font-size: 24px;">🤖</span>
                                        <strong style="color: #1f2937; font-size: 15px; margin-left: 10px;">FinOps AI Assistant</strong>
                                        <p style="margin: 5px 0 0 44px; color: #6b7280; font-size: 14px;">Personalized advice by Claude AI</p>
                                    </td>
                                </tr>
                            </table>

                            <!-- CTA Button -->
                            <table width="100%" border="0" cellspacing="0" cellpadding="0" style="margin: 30px 0;">
                                <tr>
                                    <td align="center">
                                        <a href="{app_url}/auth/login" style="display: inline-block; padding: 14px 32px; background-color: #10b981; color: #ffffff; text-decoration: none; border-radius: 6px; font-size: 16px; font-weight: 600;">
                                            🚀 Access CutCosts
                                        </a>
                                    </td>
                                </tr>
                            </table>

                            <!-- Next steps -->
                            <div style="margin: 30px 0; padding: 20px; background-color: #f0f9ff; border-left: 4px solid #2563eb; border-radius: 4px;">
                                <p style="margin: 0 0 10px; color: #1e40af; font-size: 15px; font-weight: 600;">
                                    🎯 Next steps:
                                </p>
                                <ol style="margin: 10px 0 0; padding-left: 20px; color: #1e3a8a; font-size: 14px; line-height: 1.8;">
                                    <li>Connect your AWS or Azure account</li>
                                    <li>Launch your first scan</li>
                                    <li>Discover your potential savings</li>
                                    <li>Chat with the AI assistant to optimize your costs</li>
                                </ol>
                            </div>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 30px 40px; background-color: #f9fafb; border-top: 1px solid #e5e7eb; border-radius: 0 0 8px 8px;">
                            <p style="margin: 0 0 10px; color: #6b7280; font-size: 13px; text-align: center;">
                                Need help? Check out our documentation or contact support.
                            </p>
                            <p style="margin: 0; color: #9ca3af; font-size: 12px; text-align: center; line-height: 1.5;">
                                © 2025 CutCosts. All rights reserved.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def get_welcome_email_text(full_name: str) -> str:
    """
    Get plain text version for welcome email.

    Args:
        full_name: User's full name

    Returns:
        Plain text email content
    """
    app_url = settings.FRONTEND_URL

    return f"""
🎉 Congratulations!

Your account is activated, {full_name}!

Your email address has been verified successfully. You can now access all CutCosts features:

📊 Automated scans
   Detection of orphaned AWS and Azure resources

💰 Identified savings
   Accurate waste cost estimation

🤖 FinOps AI Assistant
   Personalized advice by Claude AI

🚀 Access CutCosts: {app_url}/auth/login

🎯 Next steps:
1. Connect your AWS or Azure account
2. Launch your first scan
3. Discover your potential savings
4. Chat with the AI assistant to optimize your costs

---
Need help? Check out our documentation or contact support.
© 2025 CutCosts. All rights reserved.
"""


def send_welcome_email(email: str, full_name: str) -> bool:
    """
    Send welcome email to user after email verification.

    Args:
        email: User email address
        full_name: User's full name

    Returns:
        True if email sent successfully, False otherwise
    """
    html_content = get_welcome_email_html(full_name)
    text_content = get_welcome_email_text(full_name)

    return send_email(
        to_email=email,
        subject="🎉 Welcome to CutCosts - Your account is activated!",
        html_content=html_content,
        text_content=text_content,
    )


def get_scan_summary_email_html(
    full_name: str,
    account_name: str,
    scan_type: str,
    status: str,
    started_at: str,
    completed_at: str,
    total_resources_scanned: int = 0,
    orphan_resources_found: int = 0,
    estimated_monthly_waste: float = 0.0,
    regions_scanned: list[str] | None = None,
    error_message: str | None = None,
) -> str:
    """
    Get HTML template for scan summary email.

    Args:
        full_name: User's full name
        account_name: Cloud account name
        scan_type: Type of scan (manual or scheduled)
        status: Scan status (completed or failed)
        started_at: Scan start time (formatted string)
        completed_at: Scan completion time (formatted string)
        total_resources_scanned: Total resources scanned
        orphan_resources_found: Number of orphan resources found
        estimated_monthly_waste: Estimated monthly cost waste
        regions_scanned: List of regions scanned
        error_message: Error message if scan failed

    Returns:
        HTML email content
    """
    app_url = settings.FRONTEND_URL
    scan_type_en = "Manual" if scan_type == "manual" else "Scheduled"

    # Success template
    if status == "completed":
        regions_list = ", ".join(regions_scanned) if regions_scanned else "N/A"

        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Scan result - CutCosts</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #f3f4f6;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table width="600" border="0" cellspacing="0" cellpadding="0" style="background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 20px; text-align: center;">
                            <h1 style="margin: 0; color: #1f2937; font-size: 28px; font-weight: 700;">
                                🛡️ CutCosts
                            </h1>
                            <p style="margin: 10px 0 0; color: #6b7280; font-size: 14px;">
                                Cloud Cost Optimization
                            </p>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 20px 40px;">
                            <h2 style="margin: 0 0 20px; color: #1f2937; font-size: 22px; font-weight: 600;">
                                ✅ Scan completed successfully
                            </h2>
                            <p style="margin: 0 0 15px; color: #374151; font-size: 16px; line-height: 1.6;">
                                Hello {full_name},
                            </p>
                            <p style="margin: 0 0 15px; color: #374151; font-size: 16px; line-height: 1.6;">
                                The scan of your cloud account <strong>{account_name}</strong> ({scan_type_en.lower()} scan) is completed.
                            </p>

                            <!-- Scan Info Box -->
                            <div style="margin: 25px 0; padding: 20px; background-color: #f0f9ff; border-left: 4px solid #2563eb; border-radius: 4px;">
                                <table width="100%" border="0" cellspacing="0" cellpadding="0">
                                    <tr>
                                        <td style="padding: 8px 0;">
                                            <strong style="color: #1e40af; font-size: 15px;">Account:</strong>
                                            <span style="color: #1e3a8a; font-size: 15px; margin-left: 10px;">{account_name}</span>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 8px 0;">
                                            <strong style="color: #1e40af; font-size: 15px;">Scan type:</strong>
                                            <span style="color: #1e3a8a; font-size: 15px; margin-left: 10px;">{scan_type_en}</span>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 8px 0;">
                                            <strong style="color: #1e40af; font-size: 15px;">Duration:</strong>
                                            <span style="color: #1e3a8a; font-size: 15px; margin-left: 10px;">{started_at} → {completed_at}</span>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 8px 0;">
                                            <strong style="color: #1e40af; font-size: 15px;">Scanned regions:</strong>
                                            <span style="color: #1e3a8a; font-size: 15px; margin-left: 10px;">{regions_list}</span>
                                        </td>
                                    </tr>
                                </table>
                            </div>

                            <!-- Results Box -->
                            <div style="margin: 25px 0; padding: 20px; background-color: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 4px;">
                                <p style="margin: 0 0 15px; color: #92400e; font-size: 16px; font-weight: 600;">
                                    📊 Scan results:
                                </p>
                                <table width="100%" border="0" cellspacing="0" cellpadding="0">
                                    <tr>
                                        <td style="padding: 8px 0;">
                                            <strong style="color: #78350f; font-size: 15px;">Scanned resources:</strong>
                                            <span style="color: #92400e; font-size: 15px; margin-left: 10px;">{total_resources_scanned}</span>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 8px 0;">
                                            <strong style="color: #78350f; font-size: 15px;">Orphaned resources found:</strong>
                                            <span style="color: #92400e; font-size: 15px; margin-left: 10px; font-weight: 700;">{orphan_resources_found}</span>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 8px 0;">
                                            <strong style="color: #78350f; font-size: 15px;">Estimated monthly waste cost:</strong>
                                            <span style="color: #92400e; font-size: 18px; margin-left: 10px; font-weight: 700;">${estimated_monthly_waste:.2f}</span>
                                        </td>
                                    </tr>
                                </table>
                            </div>

                            <!-- CTA Button -->
                            <table width="100%" border="0" cellspacing="0" cellpadding="0" style="margin: 30px 0;">
                                <tr>
                                    <td align="center">
                                        <a href="{app_url}/dashboard/resources" style="display: inline-block; padding: 14px 32px; background-color: #2563eb; color: #ffffff; text-decoration: none; border-radius: 6px; font-size: 16px; font-weight: 600;">
                                            📋 View detailed results
                                        </a>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 20px 0 0; color: #6b7280; font-size: 14px; line-height: 1.6;">
                                Check the dashboard to see details for each orphaned resource and optimize your cloud costs.
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 30px 40px; background-color: #f9fafb; border-top: 1px solid #e5e7eb; border-radius: 0 0 8px 8px;">
                            <p style="margin: 0; color: #9ca3af; font-size: 12px; text-align: center; line-height: 1.5;">
                                This email was sent by <strong>CutCosts</strong><br>
                                © 2025 CutCosts. All rights reserved.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

    # Failure template
    else:
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Scan failed - CutCosts</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #f3f4f6;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table width="600" border="0" cellspacing="0" cellpadding="0" style="background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 20px; text-align: center;">
                            <h1 style="margin: 0; color: #1f2937; font-size: 28px; font-weight: 700;">
                                🛡️ CutCosts
                            </h1>
                            <p style="margin: 10px 0 0; color: #6b7280; font-size: 14px;">
                                Cloud Cost Optimization
                            </p>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 20px 40px;">
                            <h2 style="margin: 0 0 20px; color: #1f2937; font-size: 22px; font-weight: 600;">
                                ❌ Scan failed
                            </h2>
                            <p style="margin: 0 0 15px; color: #374151; font-size: 16px; line-height: 1.6;">
                                Hello {full_name},
                            </p>
                            <p style="margin: 0 0 15px; color: #374151; font-size: 16px; line-height: 1.6;">
                                The scan of your cloud account <strong>{account_name}</strong> ({scan_type_en.lower()} scan) has failed.
                            </p>

                            <!-- Error Box -->
                            <div style="margin: 25px 0; padding: 20px; background-color: #fee2e2; border-left: 4px solid #dc2626; border-radius: 4px;">
                                <p style="margin: 0 0 10px; color: #991b1b; font-size: 15px; font-weight: 600;">
                                    🚨 Error encountered:
                                </p>
                                <p style="margin: 0; color: #7f1d1d; font-size: 14px; line-height: 1.6; font-family: monospace;">
                                    {error_message or "Unknown error"}
                                </p>
                            </div>

                            <!-- Recommendations -->
                            <div style="margin: 25px 0; padding: 20px; background-color: #f0f9ff; border-left: 4px solid #2563eb; border-radius: 4px;">
                                <p style="margin: 0 0 10px; color: #1e40af; font-size: 15px; font-weight: 600;">
                                    💡 Recommendations:
                                </p>
                                <ul style="margin: 10px 0 0; padding-left: 20px; color: #1e3a8a; font-size: 14px; line-height: 1.8;">
                                    <li>Verify that your cloud credentials are still valid</li>
                                    <li>Ensure that IAM permissions are correctly configured</li>
                                    <li>Check your account's network connectivity</li>
                                    <li>Consult the documentation to resolve common errors</li>
                                </ul>
                            </div>

                            <!-- CTA Button -->
                            <table width="100%" border="0" cellspacing="0" cellpadding="0" style="margin: 30px 0;">
                                <tr>
                                    <td align="center">
                                        <a href="{app_url}/dashboard/accounts" style="display: inline-block; padding: 14px 32px; background-color: #2563eb; color: #ffffff; text-decoration: none; border-radius: 6px; font-size: 16px; font-weight: 600;">
                                            ⚙️ Check my cloud accounts
                                        </a>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 20px 0 0; color: #6b7280; font-size: 14px; line-height: 1.6;">
                                If the problem persists, contact our technical support for assistance.
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 30px 40px; background-color: #f9fafb; border-top: 1px solid #e5e7eb; border-radius: 0 0 8px 8px;">
                            <p style="margin: 0; color: #9ca3af; font-size: 12px; text-align: center; line-height: 1.5;">
                                This email was sent by <strong>CutCosts</strong><br>
                                © 2025 CutCosts. All rights reserved.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def get_scan_summary_email_text(
    full_name: str,
    account_name: str,
    scan_type: str,
    status: str,
    started_at: str,
    completed_at: str,
    total_resources_scanned: int = 0,
    orphan_resources_found: int = 0,
    estimated_monthly_waste: float = 0.0,
    regions_scanned: list[str] | None = None,
    error_message: str | None = None,
) -> str:
    """
    Get plain text version for scan summary email.

    Args:
        full_name: User's full name
        account_name: Cloud account name
        scan_type: Type of scan (manual or scheduled)
        status: Scan status (completed or failed)
        started_at: Scan start time (formatted string)
        completed_at: Scan completion time (formatted string)
        total_resources_scanned: Total resources scanned
        orphan_resources_found: Number of orphan resources found
        estimated_monthly_waste: Estimated monthly cost waste
        regions_scanned: List of regions scanned
        error_message: Error message if scan failed

    Returns:
        Plain text email content
    """
    app_url = settings.FRONTEND_URL
    scan_type_en = "Manual" if scan_type == "manual" else "Scheduled"

    # Success template
    if status == "completed":
        regions_list = ", ".join(regions_scanned) if regions_scanned else "N/A"

        return f"""
✅ Scan completed successfully

Hello {full_name},

The scan of your cloud account {account_name} ({scan_type_en.lower()} scan) is completed.

📋 Scan information:
- Account: {account_name}
- Scan type: {scan_type_en}
- Duration: {started_at} → {completed_at}
- Scanned regions: {regions_list}

📊 Scan results:
- Scanned resources: {total_resources_scanned}
- Orphaned resources found: {orphan_resources_found}
- Estimated monthly waste cost: ${estimated_monthly_waste:.2f}

Check the dashboard to see details for each orphaned resource and optimize your cloud costs.

👉 View detailed results: {app_url}/dashboard/resources

---
This email was sent by CutCosts
© 2025 CutCosts. All rights reserved.
"""

    # Failure template
    else:
        return f"""
❌ Scan failed

Hello {full_name},

The scan of your cloud account {account_name} ({scan_type_en.lower()} scan) has failed.

🚨 Error encountered:
{error_message or "Unknown error"}

💡 Recommendations:
- Verify that your cloud credentials are still valid
- Ensure that IAM permissions are correctly configured
- Check your account's network connectivity
- Consult the documentation to resolve common errors

If the problem persists, contact our technical support for assistance.

👉 Check my cloud accounts: {app_url}/dashboard/accounts

---
This email was sent by CutCosts
© 2025 CutCosts. All rights reserved.
"""


def send_scan_summary_email(
    email: str,
    full_name: str,
    account_name: str,
    scan_type: str,
    status: str,
    started_at: str,
    completed_at: str,
    total_resources_scanned: int = 0,
    orphan_resources_found: int = 0,
    estimated_monthly_waste: float = 0.0,
    regions_scanned: list[str] | None = None,
    error_message: str | None = None,
) -> bool:
    """
    Send scan summary email to user after scan completion.

    Args:
        email: User email address
        full_name: User's full name
        account_name: Cloud account name
        scan_type: Type of scan (manual or scheduled)
        status: Scan status (completed or failed)
        started_at: Scan start time (formatted string)
        completed_at: Scan completion time (formatted string)
        total_resources_scanned: Total resources scanned
        orphan_resources_found: Number of orphan resources found
        estimated_monthly_waste: Estimated monthly cost waste
        regions_scanned: List of regions scanned
        error_message: Error message if scan failed

    Returns:
        True if email sent successfully, False otherwise
    """
    html_content = get_scan_summary_email_html(
        full_name=full_name,
        account_name=account_name,
        scan_type=scan_type,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        total_resources_scanned=total_resources_scanned,
        orphan_resources_found=orphan_resources_found,
        estimated_monthly_waste=estimated_monthly_waste,
        regions_scanned=regions_scanned,
        error_message=error_message,
    )
    text_content = get_scan_summary_email_text(
        full_name=full_name,
        account_name=account_name,
        scan_type=scan_type,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        total_resources_scanned=total_resources_scanned,
        orphan_resources_found=orphan_resources_found,
        estimated_monthly_waste=estimated_monthly_waste,
        regions_scanned=regions_scanned,
        error_message=error_message,
    )

    # Determine subject based on status
    if status == "completed":
        subject = f"✅ Scan completed - {account_name} - CutCosts"
    else:
        subject = f"❌ Scan failed - {account_name} - CutCosts"

    return send_email(
        to_email=email,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
    )
