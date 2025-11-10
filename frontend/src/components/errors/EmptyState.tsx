import { Cloud, Database, FileX, FolderX, Inbox } from "lucide-react";
import { EmptyStateProps } from "@/types/errors";

/**
 * Empty State Component
 *
 * Displays a message when there's no data to show.
 * Used for empty lists, no search results, or initial states.
 *
 * @example
 * ```tsx
 * <EmptyState
 *   icon={Database}
 *   title="Aucun compte cloud"
 *   description="Ajoutez votre premier compte cloud pour commencer à détecter les ressources orphelines."
 *   action={{
 *     label: "Ajouter un compte",
 *     onClick: () => router.push('/dashboard/accounts/new'),
 *     variant: "primary"
 *   }}
 * />
 * ```
 */
export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
}: EmptyStateProps) {
  const ActionIcon = action?.icon;

  return (
    <div className="flex min-h-[400px] flex-col items-center justify-center rounded-lg border border-dashed border-gray-300 bg-gray-50/50 p-8 text-center">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-gray-100">
        <Icon className="h-8 w-8 text-gray-400" strokeWidth={1.5} />
      </div>

      <h3 className="mb-2 text-lg font-semibold text-gray-900">{title}</h3>

      {description && (
        <p className="mb-6 max-w-md text-sm text-gray-600">{description}</p>
      )}

      {action && (
        <button
          onClick={action.onClick}
          className={getButtonClasses(action.variant)}
        >
          {ActionIcon && <ActionIcon className="h-4 w-4" />}
          {action.label}
        </button>
      )}
    </div>
  );
}

function getButtonClasses(variant: "primary" | "secondary" | "outline" = "primary"): string {
  const baseClasses =
    "inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2";

  switch (variant) {
    case "primary":
      return `${baseClasses} bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500`;
    case "secondary":
      return `${baseClasses} bg-gray-600 text-white hover:bg-gray-700 focus:ring-gray-500`;
    case "outline":
      return `${baseClasses} border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 focus:ring-gray-500`;
    default:
      return `${baseClasses} bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500`;
  }
}

// Export commonly used icons for convenience
export const EmptyStateIcons = {
  Inbox,
  Database,
  Cloud,
  FileX,
  FolderX,
};
