/**
 * Dialog Store (Zustand)
 *
 * Global state management for custom dialogs.
 * Handles dialog visibility, type, options, and promise-based resolution.
 */

import { create } from 'zustand';
import type { DialogStore, DialogOptions, DialogType } from '@/types/dialog';

/**
 * Helper function to normalize dialog options
 */
const normalizeOptions = (input: string | DialogOptions): DialogOptions => {
  if (typeof input === 'string') {
    return { message: input };
  }
  return input;
};

export const useDialogStore = create<DialogStore>((set, get) => ({
  // Initial state
  isOpen: false,
  type: 'alert',
  options: { message: '' },
  resolve: undefined,

  /**
   * Show an alert dialog (single OK button)
   */
  showAlert: (input: string | DialogOptions) => {
    return new Promise<void>((resolve) => {
      set({
        isOpen: true,
        type: 'alert',
        options: normalizeOptions(input),
        resolve: (confirmed) => {
          resolve();
        },
      });
    });
  },

  /**
   * Show a confirm dialog (Cancel + Confirm buttons)
   */
  showConfirm: (input: string | DialogOptions) => {
    return new Promise<boolean>((resolve) => {
      set({
        isOpen: true,
        type: 'confirm',
        options: normalizeOptions(input),
        resolve,
      });
    });
  },

  /**
   * Show a destructive confirm dialog (Cancel + Delete buttons, red styling)
   */
  showDestructiveConfirm: (input: string | DialogOptions) => {
    return new Promise<boolean>((resolve) => {
      set({
        isOpen: true,
        type: 'destructive',
        options: normalizeOptions(input),
        resolve,
      });
    });
  },

  /**
   * Handle confirm action
   */
  handleConfirm: () => {
    const { resolve } = get();
    if (resolve) {
      resolve(true);
    }
    set({
      isOpen: false,
      resolve: undefined,
    });
  },

  /**
   * Handle cancel action
   */
  handleCancel: () => {
    const { resolve } = get();
    if (resolve) {
      resolve(false);
    }
    set({
      isOpen: false,
      resolve: undefined,
    });
  },

  /**
   * Close the dialog without resolving (for alert dialogs)
   */
  close: () => {
    const { resolve, type } = get();
    // For alert dialogs, close is the same as confirm
    if (type === 'alert' && resolve) {
      resolve(true);
    }
    set({
      isOpen: false,
      resolve: undefined,
    });
  },
}));
