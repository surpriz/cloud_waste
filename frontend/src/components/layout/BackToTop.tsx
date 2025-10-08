"use client";

import { useState, useEffect } from "react";
import { ArrowUp } from "lucide-react";

export function BackToTop() {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const toggleVisibility = () => {
      // Try to find a scrollable main element first
      const mainElement = document.querySelector("main");
      const scrollTop = mainElement
        ? mainElement.scrollTop
        : window.pageYOffset || document.documentElement.scrollTop;

      // Show button when page is scrolled down 300px
      if (scrollTop > 300) {
        setIsVisible(true);
      } else {
        setIsVisible(false);
      }
    };

    // Add scroll event listeners for both main element and window
    const mainElement = document.querySelector("main");

    if (mainElement) {
      mainElement.addEventListener("scroll", toggleVisibility);
    }
    window.addEventListener("scroll", toggleVisibility);

    // Check initial scroll position
    toggleVisibility();

    // Clean up
    return () => {
      if (mainElement) {
        mainElement.removeEventListener("scroll", toggleVisibility);
      }
      window.removeEventListener("scroll", toggleVisibility);
    };
  }, []);

  const scrollToTop = () => {
    // Try to find a scrollable main element first
    const mainElement = document.querySelector("main");

    if (mainElement && mainElement.scrollTop > 0) {
      mainElement.scrollTo({
        top: 0,
        behavior: "smooth",
      });
    } else {
      window.scrollTo({
        top: 0,
        behavior: "smooth",
      });
    }
  };

  return (
    <>
      {isVisible && (
        <button
          onClick={scrollToTop}
          className="fixed bottom-8 right-8 z-50 flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-r from-blue-600 to-purple-600 text-white shadow-lg transition-all hover:scale-110 hover:shadow-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          aria-label="Back to top"
        >
          <ArrowUp className="h-5 w-5" />
        </button>
      )}
    </>
  );
}
