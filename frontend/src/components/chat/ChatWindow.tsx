/**
 * ChatWindow component - Main chat interface with messages
 */

"use client";

import { useEffect, useRef } from "react";
import { useChatStore } from "@/stores/useChatStore";
import { ChatMessage } from "./ChatMessage";
import { ChatInput } from "./ChatInput";
import { SuggestedQuestions } from "./SuggestedQuestions";
import { Loader2 } from "lucide-react";

export function ChatWindow() {
  const {
    currentConversation,
    isStreaming,
    streamingMessage,
    sendMessage,
    createNewConversation,
    isLoading,
  } = useChatStore();

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive or streaming updates
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [currentConversation?.messages, streamingMessage]);

  const handleSendMessage = async (message: string) => {
    try {
      // Create conversation automatically if none exists
      if (!currentConversation) {
        await createNewConversation("New Conversation");
        // Wait a bit for the conversation to be created
        await new Promise(resolve => setTimeout(resolve, 100));
      }
      await sendMessage(message);
    } catch (error) {
      console.error("Failed to send message:", error);
    }
  };

  // Show suggested questions if no conversation is selected or conversation is empty
  const showSuggestions =
    !currentConversation ||
    !currentConversation.messages ||
    currentConversation.messages.length === 0;

  if (showSuggestions && !isLoading) {
    return (
      <div className="flex flex-col h-full">
        <SuggestedQuestions onSelect={handleSendMessage} />
        <ChatInput
          onSend={handleSendMessage}
          disabled={isStreaming}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto p-4 space-y-4"
      >
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="h-8 w-8 animate-spin text-blue-400" />
          </div>
        ) : (
          <>
            {currentConversation?.messages?.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}

            {/* Streaming message */}
            {isStreaming && streamingMessage && (
              <ChatMessage
                message={{
                  id: "streaming",
                  conversation_id: currentConversation?.id || "",
                  role: "assistant",
                  content: streamingMessage,
                  created_at: new Date().toISOString(),
                }}
                isStreaming={true}
              />
            )}

            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input area */}
      <ChatInput
        onSend={handleSendMessage}
        disabled={isStreaming}
        placeholder={
          isStreaming
            ? "AI is thinking..."
            : "Ask about your cloud resources..."
        }
      />
    </div>
  );
}
