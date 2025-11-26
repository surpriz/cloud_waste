/**
 * Dialog Component
 *
 * Custom styled dialog component matching CutCost design system.
 * Supports 3 variants: alert, confirm, and destructive.
 */

'use client';

import React, { useEffect, useRef } from 'react';
import { Info, AlertCircle, AlertTriangle } from 'lucide-react';
import type { DialogType, DialogOptions } from '@/types/dialog';

interface DialogProps {
  isOpen: boolean;
  type: DialogType;
  options: DialogOptions;
  onConfirm: () => void;
  onCancel: () => void;
}

export const Dialog: React.FC<DialogProps> = ({
  isOpen,
  type,
  options,
  onConfirm,
  onCancel,
}) => {
  const confirmButtonRef = useRef<HTMLButtonElement>(null);

  // Handle keyboard events
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onCancel();
      } else if (event.key === 'Enter') {
        event.preventDefault();
        onConfirm();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onConfirm, onCancel]);

  // Auto-focus confirm button when dialog opens
  useEffect(() => {
    if (isOpen && confirmButtonRef.current) {
      confirmButtonRef.current.focus();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  // Handle overlay click
  const handleOverlayClick = (event: React.MouseEvent<HTMLDivElement>) => {
    // For destructive dialogs, don't close on overlay click (force conscious choice)
    if (type === 'destructive') return;

    // Only close if clicking the overlay itself, not its children
    if (event.target === event.currentTarget) {
      onCancel();
    }
  };

  // Get icon component based on dialog type
  const Icon = type === 'destructive' ? AlertTriangle : type === 'confirm' ? AlertCircle : Info;

  // Get icon color class
  const iconColorClass =
    type === 'destructive' ? 'text-red-600' : 'text-blue-600';

  // Get border color class
  const borderColorClass =
    type === 'destructive' ? 'border-red-300' : 'border-gray-200';

  // Get default button texts
  const confirmText =
    options.confirmText ||
    (type === 'alert' ? 'OK' : type === 'destructive' ? 'Supprimer' : 'Confirmer');
  const cancelText = options.cancelText || 'Annuler';
  const warningText = options.warningText || 'Action irréversible';

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100] animate-fade-in"
        onClick={handleOverlayClick}
        aria-hidden="true"
      />

      {/* Dialog Container */}
      <div
        className="fixed inset-0 z-[101] flex items-center justify-center p-4"
        onClick={handleOverlayClick}
      >
        {/* Dialog Card */}
        <div
          className={`w-full max-w-md bg-white rounded-2xl border-2 ${borderColorClass} shadow-xl animate-scale-in pointer-events-auto`}
          role="dialog"
          aria-modal="true"
          aria-labelledby={options.title ? 'dialog-title' : undefined}
          aria-describedby="dialog-message"
        >
          {/* Content */}
          <div className="p-6">
            {/* Icon + Title Section */}
            <div className="flex items-start gap-4 mb-4">
              {/* Icon */}
              <div className="flex-shrink-0 mt-0.5">
                <Icon className={`h-6 w-6 ${iconColorClass}`} aria-hidden="true" />
              </div>

              {/* Title + Message */}
              <div className="flex-1">
                {options.title && (
                  <h2
                    id="dialog-title"
                    className="text-lg font-semibold text-gray-900 mb-2"
                  >
                    {options.title}
                  </h2>
                )}

                <p
                  id="dialog-message"
                  className="text-gray-700 leading-relaxed"
                >
                  {options.message}
                </p>

                {/* Warning badge for destructive dialogs */}
                {type === 'destructive' && (
                  <div className="mt-3 inline-flex items-center gap-1.5 px-3 py-1 bg-red-50 border border-red-200 rounded-lg">
                    <span className="text-red-600 font-medium text-sm">
                      ⚠️ {warningText}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Buttons */}
            <div className="flex gap-3 mt-6">
              {/* Cancel button (for confirm and destructive dialogs) */}
              {type !== 'alert' && (
                <button
                  type="button"
                  onClick={onCancel}
                  className="flex-1 px-4 py-2 border-2 border-gray-300 bg-white text-gray-700 hover:bg-gray-50 rounded-lg font-semibold transition-colors"
                >
                  {cancelText}
                </button>
              )}

              {/* Confirm button */}
              <button
                ref={confirmButtonRef}
                type="button"
                onClick={onConfirm}
                className={`${
                  type === 'alert' ? 'w-full' : 'flex-1'
                } px-4 py-2 ${
                  type === 'destructive'
                    ? 'bg-red-600 hover:bg-red-700'
                    : 'bg-blue-600 hover:bg-blue-700'
                } text-white rounded-lg font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 ${
                  type === 'destructive' ? 'focus:ring-red-500' : 'focus:ring-blue-500'
                }`}
              >
                {confirmText}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};
