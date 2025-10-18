/**
 * ChatMessage component - Displays a single chat message
 */

import type { ChatMessage as ChatMessageType } from "@/types";
import { Bot, User } from "lucide-react";

interface ChatMessageProps {
  message: ChatMessageType;
  isStreaming?: boolean;
}

export function ChatMessage({ message, isStreaming = false }: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <div
      className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"} mb-4`}
    >
      {/* Avatar */}
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
          isUser
            ? "bg-blue-600 text-white"
            : "bg-gray-700 text-gray-200"
        }`}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* Message bubble */}
      <div
        className={`max-w-[80%] rounded-lg px-4 py-2 ${
          isUser
            ? "bg-blue-600 text-white"
            : "bg-gray-800 text-gray-100"
        }`}
      >
        {/* Message content with markdown-like formatting */}
        <div className="prose prose-invert max-w-none prose-p:my-1 prose-headings:mt-3 prose-headings:mb-2">
          <MessageContent content={message.content} isStreaming={isStreaming} />
        </div>

        {/* Timestamp and message_metadata */}
        <div className={`mt-2 text-xs ${isUser ? "text-blue-200" : "text-gray-400"}`}>
          {new Date(message.created_at).toLocaleTimeString("fr-FR", {
            hour: "2-digit",
            minute: "2-digit",
          })}
          {message.message_metadata?.cost_usd && (
            <span className="ml-2">
              (${(message.message_metadata.cost_usd as number).toFixed(4)})
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * MessageContent - Renders message content with basic markdown support
 */
function MessageContent({ content, isStreaming }: { content: string; isStreaming: boolean }) {
  // Simple markdown-like rendering
  const renderContent = (text: string) => {
    // Split by double newline for paragraphs
    const paragraphs = text.split("\n\n");

    return paragraphs.map((paragraph, pIndex) => {
      const lines = paragraph.split("\n");

      return (
        <div key={pIndex} className="mb-2">
          {lines.map((line, lIndex) => {
            // Headers
            if (line.startsWith("### ")) {
              return (
                <h3 key={lIndex} className="text-lg font-semibold mt-3 mb-1">
                  {line.substring(4)}
                </h3>
              );
            }
            if (line.startsWith("## ")) {
              return (
                <h2 key={lIndex} className="text-xl font-bold mt-3 mb-2">
                  {line.substring(3)}
                </h2>
              );
            }

            // Bullet points
            if (line.startsWith("- ") || line.startsWith("* ")) {
              return (
                <li key={lIndex} className="ml-4">
                  {line.substring(2)}
                </li>
              );
            }

            // Numbered lists
            const numberedMatch = line.match(/^(\d+)\.\s/);
            if (numberedMatch) {
              return (
                <li key={lIndex} className="ml-4 list-decimal">
                  {line.substring(numberedMatch[0].length)}
                </li>
              );
            }

            // Bold text **text**
            const boldRegex = /\*\*(.*?)\*\*/g;
            const parts = line.split(boldRegex);

            return (
              <p key={lIndex} className="my-1">
                {parts.map((part, i) =>
                  i % 2 === 1 ? (
                    <strong key={i} className="font-bold">
                      {part}
                    </strong>
                  ) : (
                    part
                  )
                )}
              </p>
            );
          })}
        </div>
      );
    });
  };

  return (
    <div>
      {renderContent(content)}
      {isStreaming && <span className="inline-block w-2 h-4 ml-1 bg-current animate-pulse" />}
    </div>
  );
}
