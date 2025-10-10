"use client";

import { useEffect, useState } from "react";
import { X, CheckCircle2, XCircle } from "lucide-react";
import type { Notification } from "@/hooks/useNotifications";

interface ToastProps {
  notification: Notification;
  onClose: () => void;
  duration?: number;
}

export function Toast({ notification, onClose, duration = 3000 }: ToastProps) {
  const [progress, setProgress] = useState(0);
  const [isExiting, setIsExiting] = useState(false);

  const { message, type } = notification;
  const isSuccess = type === "success";

  useEffect(() => {
    // Progress bar animation
    const startTime = Date.now();
    const interval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const newProgress = Math.min((elapsed / duration) * 100, 100);
      setProgress(newProgress);

      if (newProgress >= 100) {
        clearInterval(interval);
      }
    }, 16); // ~60 FPS

    return () => clearInterval(interval);
  }, [duration]);

  const handleClose = () => {
    setIsExiting(true);
    setTimeout(() => {
      onClose();
    }, 200); // Match animation duration
  };

  return (
    <div
      className={`
        fixed top-4 right-4 z-50
        w-96 max-w-[calc(100vw-2rem)]
        rounded-xl border-2 shadow-2xl
        overflow-hidden
        transition-all duration-200
        ${isExiting ? "opacity-0 translate-x-full" : "opacity-100 translate-x-0"}
        ${
          isSuccess
            ? "bg-green-50 border-green-300"
            : "bg-red-50 border-red-300"
        }
        animate-in slide-in-from-right-5
      `}
      role="alert"
      aria-live="polite"
    >
      {/* Main content */}
      <div className="flex items-start gap-3 p-4 pr-12">
        {/* Icon */}
        <div className="flex-shrink-0 mt-0.5">
          {isSuccess ? (
            <CheckCircle2 className="h-5 w-5 text-green-600" />
          ) : (
            <XCircle className="h-5 w-5 text-red-600" />
          )}
        </div>

        {/* Message */}
        <div className={`flex-1 font-semibold ${isSuccess ? "text-green-800" : "text-red-800"}`}>
          {message}
        </div>

        {/* Close button */}
        <button
          onClick={handleClose}
          className={`
            absolute top-3 right-3
            p-1 rounded-lg
            transition-colors
            ${
              isSuccess
                ? "hover:bg-green-200 text-green-700"
                : "hover:bg-red-200 text-red-700"
            }
          `}
          aria-label="Close notification"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-black/10">
        <div
          className={`h-full transition-all duration-100 ease-linear ${
            isSuccess ? "bg-green-500" : "bg-red-500"
          }`}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}
