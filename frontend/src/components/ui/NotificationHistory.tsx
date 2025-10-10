"use client";

import { useState, useRef, useEffect } from "react";
import { Bell, CheckCircle2, XCircle, Trash2 } from "lucide-react";
import type { Notification } from "@/hooks/useNotifications";

interface NotificationHistoryProps {
  notifications: Notification[];
  onClearHistory: () => void;
}

export function NotificationHistory({ notifications, onClearHistory }: NotificationHistoryProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  const formatTimestamp = (date: Date) => {
    const now = new Date();
    const diff = Math.floor((now.getTime() - date.getTime()) / 1000); // seconds

    if (diff < 60) return "Just now";
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  };

  const handleClearAll = () => {
    if (confirm("Clear all notification history?")) {
      onClearHistory();
      setIsOpen(false);
    }
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Bell button with badge */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 rounded-lg hover:bg-gray-100 transition-colors"
        aria-label="Notification history"
        aria-expanded={isOpen}
      >
        <Bell className="h-5 w-5 text-gray-600" />

        {/* Badge with notification count */}
        {notifications.length > 0 && (
          <span className="absolute top-0 right-0 flex h-5 w-5 items-center justify-center rounded-full bg-blue-600 text-[10px] font-bold text-white">
            {notifications.length}
          </span>
        )}
      </button>

      {/* Dropdown panel */}
      {isOpen && (
        <div
          className="
            absolute top-full right-0 mt-2
            w-96 max-w-[calc(100vw-2rem)]
            bg-white rounded-xl border-2 border-gray-200 shadow-2xl
            overflow-hidden
            animate-in slide-in-from-top-2 duration-200
            z-50
          "
        >
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-gray-200 bg-gray-50">
            <div className="flex items-center gap-2">
              <Bell className="h-5 w-5 text-gray-700" />
              <h3 className="font-bold text-gray-900">
                Notifications {notifications.length > 0 && `(${notifications.length})`}
              </h3>
            </div>

            {notifications.length > 0 && (
              <button
                onClick={handleClearAll}
                className="flex items-center gap-1 px-3 py-1 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors"
              >
                <Trash2 className="h-4 w-4" />
                Clear All
              </button>
            )}
          </div>

          {/* Notification list */}
          {notifications.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              <Bell className="h-12 w-12 mx-auto mb-2 text-gray-300" />
              <p className="text-sm">No notifications yet</p>
            </div>
          ) : (
            <div className="max-h-96 overflow-y-auto">
              {notifications.map((notification, index) => (
                <div
                  key={notification.id}
                  className={`
                    p-4 flex items-start gap-3
                    hover:bg-gray-50 transition-colors
                    ${index < notifications.length - 1 ? "border-b border-gray-100" : ""}
                  `}
                >
                  {/* Icon */}
                  <div className="flex-shrink-0 mt-0.5">
                    {notification.type === "success" ? (
                      <CheckCircle2 className="h-5 w-5 text-green-600" />
                    ) : (
                      <XCircle className="h-5 w-5 text-red-600" />
                    )}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <p
                      className={`text-sm font-medium ${
                        notification.type === "success" ? "text-green-800" : "text-red-800"
                      }`}
                    >
                      {notification.message}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      {formatTimestamp(notification.timestamp)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
