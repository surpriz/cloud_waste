/**
 * Dialog Types
 *
 * Type definitions for the custom dialog system.
 */

export type DialogType = 'alert' | 'confirm' | 'destructive';

export interface DialogOptions {
  /**
   * Dialog title (optional)
   */
  title?: string;

  /**
   * Dialog message content
   */
  message: string;

  /**
   * Text for the confirm/primary button
   * @default "OK" for alert, "Confirmer" for confirm, "Supprimer" for destructive
   */
  confirmText?: string;

  /**
   * Text for the cancel/secondary button (not used for alert dialogs)
   * @default "Annuler"
   */
  cancelText?: string;

  /**
   * Warning text for destructive dialogs (shown as a badge)
   * @default "Action irréversible"
   */
  warningText?: string;
}

export interface DialogState {
  /**
   * Whether the dialog is currently visible
   */
  isOpen: boolean;

  /**
   * Type of dialog
   */
  type: DialogType;

  /**
   * Dialog options (title, message, button texts)
   */
  options: DialogOptions;

  /**
   * Promise resolver for confirm/cancel
   */
  resolve?: (value: boolean) => void;
}

export interface DialogStore extends DialogState {
  /**
   * Show an alert dialog (single OK button)
   */
  showAlert: (message: string | DialogOptions) => Promise<void>;

  /**
   * Show a confirm dialog (Cancel + Confirm buttons)
   */
  showConfirm: (options: string | DialogOptions) => Promise<boolean>;

  /**
   * Show a destructive confirm dialog (Cancel + Delete buttons, red styling)
   */
  showDestructiveConfirm: (options: string | DialogOptions) => Promise<boolean>;

  /**
   * Handle confirm action
   */
  handleConfirm: () => void;

  /**
   * Handle cancel action
   */
  handleCancel: () => void;

  /**
   * Close the dialog without resolving
   */
  close: () => void;
}
