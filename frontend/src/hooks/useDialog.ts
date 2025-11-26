/**
 * useDialog Hook
 *
 * Developer-friendly API for showing dialogs.
 * Wraps the Zustand store methods for easy usage.
 */

import { useDialogStore } from '@/stores/useDialogStore';
import type { DialogOptions } from '@/types/dialog';

export const useDialog = () => {
  const showAlert = useDialogStore((state) => state.showAlert);
  const showConfirm = useDialogStore((state) => state.showConfirm);
  const showDestructiveConfirm = useDialogStore((state) => state.showDestructiveConfirm);

  return {
    /**
     * Show an alert dialog with a single OK button
     *
     * @example
     * await showAlert("Please select an account");
     *
     * @example
     * await showAlert({ title: "Success", message: "Account created!" });
     */
    showAlert,

    /**
     * Show a confirmation dialog with Cancel and Confirm buttons
     *
     * @returns Promise<boolean> - true if confirmed, false if cancelled
     *
     * @example
     * const confirmed = await showConfirm("Start scanning all accounts?");
     * if (confirmed) {
     *   startScan();
     * }
     *
     * @example
     * const confirmed = await showConfirm({
     *   title: "Confirm Action",
     *   message: "Are you sure?",
     *   confirmText: "Yes, proceed"
     * });
     */
    showConfirm,

    /**
     * Show a destructive confirmation dialog with red styling
     * Used for delete actions and other irreversible operations
     *
     * @returns Promise<boolean> - true if confirmed, false if cancelled
     *
     * @example
     * const confirmed = await showDestructiveConfirm("Delete this scan?");
     * if (confirmed) {
     *   deleteScan();
     * }
     *
     * @example
     * const confirmed = await showDestructiveConfirm({
     *   title: "Delete Account",
     *   message: "This action cannot be undone.",
     *   confirmText: "Delete",
     *   warningText: "Action irréversible"
     * });
     */
    showDestructiveConfirm,
  };
};
