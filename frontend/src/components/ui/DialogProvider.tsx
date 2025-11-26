/**
 * DialogProvider Component
 *
 * Provider that subscribes to the dialog store and renders the active dialog.
 * Should be added to the root layout to enable dialogs throughout the app.
 */

'use client';

import React from 'react';
import { Dialog } from './Dialog';
import { useDialogStore } from '@/stores/useDialogStore';

export const DialogProvider: React.FC = () => {
  const { isOpen, type, options, handleConfirm, handleCancel } = useDialogStore();

  return (
    <Dialog
      isOpen={isOpen}
      type={type}
      options={options}
      onConfirm={handleConfirm}
      onCancel={handleCancel}
    />
  );
};
