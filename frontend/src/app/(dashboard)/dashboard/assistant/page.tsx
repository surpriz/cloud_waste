/**
 * AI Assistant page - Chat interface with FinOps AI
 */

"use client";

import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { ChatWindow } from "@/components/chat/ChatWindow";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

export default function AssistantPage() {
  return (
    <div className="flex h-[calc(100vh-4rem)] bg-gray-900">
      <ChatSidebar />
      <div className="flex-1 flex flex-col">
        {/* Header with back button */}
        <div className="bg-gray-800 border-b border-gray-700 px-6 py-3 flex items-center gap-3">
          <Link
            href="/dashboard"
            className="flex items-center gap-2 text-gray-300 hover:text-white transition-colors"
          >
            <ArrowLeft className="h-5 w-5" />
            <span className="text-sm font-medium">Retour au Dashboard</span>
          </Link>
          <div className="h-5 w-px bg-gray-600 mx-2" />
          <h1 className="text-lg font-semibold text-white">AI Assistant FinOps</h1>
        </div>

        {/* Chat content */}
        <div className="flex-1 overflow-hidden">
          <ChatWindow />
        </div>
      </div>
    </div>
  );
}
