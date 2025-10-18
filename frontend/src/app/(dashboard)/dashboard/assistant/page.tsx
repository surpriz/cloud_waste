/**
 * AI Assistant page - Chat interface with FinOps AI
 */

"use client";

import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { ChatWindow } from "@/components/chat/ChatWindow";

export default function AssistantPage() {
  return (
    <div className="flex h-[calc(100vh-4rem)] bg-gray-900">
      <ChatSidebar />
      <div className="flex-1">
        <ChatWindow />
      </div>
    </div>
  );
}
