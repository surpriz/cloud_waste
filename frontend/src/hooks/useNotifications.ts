"use client";

import { useState, useCallback, useRef, useEffect } from "react";

export type NotificationType = "success" | "error";

export interface Notification {
  id: string;
  message: string;
  type: NotificationType;
  timestamp: Date;
}

interface UseNotificationsReturn {
  currentNotification: Notification | null;
  history: Notification[];
  showSuccess: (message: string) => void;
  showError: (message: string) => void;
  dismiss: () => void;
  clearHistory: () => void;
}

const MAX_HISTORY = 5;

export function useNotifications(): UseNotificationsReturn {
  const [currentNotification, setCurrentNotification] = useState<Notification | null>(null);
  const [history, setHistory] = useState<Notification[]>([]);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const successAudioRef = useRef<HTMLAudioElement | null>(null);
  const errorAudioRef = useRef<HTMLAudioElement | null>(null);

  // Initialize audio elements
  useEffect(() => {
    if (typeof window !== "undefined") {
      successAudioRef.current = new Audio("/sounds/success.mp3");
      errorAudioRef.current = new Audio("/sounds/error.mp3");

      // Preload audio for better performance
      successAudioRef.current.preload = "auto";
      errorAudioRef.current.preload = "auto";

      // Set volume to 50% (adjust as needed)
      successAudioRef.current.volume = 0.5;
      errorAudioRef.current.volume = 0.5;
    }

    return () => {
      // Cleanup
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const playSound = useCallback((type: NotificationType) => {
    try {
      const audio = type === "success" ? successAudioRef.current : errorAudioRef.current;
      if (audio) {
        // Reset audio to start if already playing
        audio.currentTime = 0;
        audio.play().catch((error) => {
          // Silently fail if user hasn't interacted with page yet (browser policy)
          console.debug("Audio play failed:", error);
        });
      }
    } catch (error) {
      console.debug("Audio playback error:", error);
    }
  }, []);

  const addToHistory = useCallback((notification: Notification) => {
    setHistory((prev) => {
      const newHistory = [notification, ...prev].slice(0, MAX_HISTORY);
      return newHistory;
    });
  }, []);

  const showNotification = useCallback(
    (message: string, type: NotificationType) => {
      // Clear any existing timeout
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }

      const notification: Notification = {
        id: `${Date.now()}-${Math.random()}`,
        message,
        type,
        timestamp: new Date(),
      };

      setCurrentNotification(notification);
      addToHistory(notification);
      playSound(type);

      // Auto-dismiss after 3 seconds
      timeoutRef.current = setTimeout(() => {
        setCurrentNotification(null);
      }, 3000);
    },
    [addToHistory, playSound]
  );

  const showSuccess = useCallback(
    (message: string) => {
      showNotification(message, "success");
    },
    [showNotification]
  );

  const showError = useCallback(
    (message: string) => {
      showNotification(message, "error");
    },
    [showNotification]
  );

  const dismiss = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    setCurrentNotification(null);
  }, []);

  const clearHistory = useCallback(() => {
    setHistory([]);
  }, []);

  return {
    currentNotification,
    history,
    showSuccess,
    showError,
    dismiss,
    clearHistory,
  };
}
