/**
 * ChatSidebar component - Lists conversations
 */

"use client";

import { useEffect } from "react";
import { MessageSquare, Plus, Trash2 } from "lucide-react";
import { useChatStore } from "@/stores/useChatStore";
import { useDialog } from "@/hooks/useDialog";

export function ChatSidebar() {
  const {
    conversations,
    currentConversation,
    loadConversations,
    selectConversation,
    createNewConversation,
    deleteConversation,
    isLoading,
  } = useChatStore();
  const { showDestructiveConfirm } = useDialog();

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const handleNewConversation = async () => {
    try {
      await createNewConversation();
    } catch (error) {
      console.error("Failed to create conversation:", error);
    }
  };

  const handleSelectConversation = async (id: string) => {
    try {
      await selectConversation(id);
    } catch (error) {
      console.error("Failed to select conversation:", error);
    }
  };

  const handleDeleteConversation = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const confirmed = await showDestructiveConfirm({
      title: "Delete Conversation",
      message: "Are you sure you want to delete this conversation?",
      confirmText: "Delete",
    });

    if (confirmed) {
      try {
        await deleteConversation(id);
      } catch (error) {
        console.error("Failed to delete conversation:", error);
      }
    }
  };

  return (
    <div className="flex h-full w-64 flex-col border-r border-gray-800 bg-gray-900">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-800 p-4">
        <h2 className="text-lg font-semibold text-white">Conversations</h2>
        <button
          onClick={handleNewConversation}
          disabled={isLoading}
          className="rounded-lg bg-blue-600 p-2 text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
          title="New conversation"
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>

      {/* Conversations list */}
      <div className="flex-1 overflow-y-auto">
        {isLoading && conversations.length === 0 ? (
          <div className="p-4 text-center text-gray-400">Loading...</div>
        ) : conversations.length === 0 ? (
          <div className="p-4 text-center text-gray-400">
            <MessageSquare className="mx-auto h-12 w-12 mb-2 opacity-50" />
            <p>No conversations yet</p>
            <p className="text-sm mt-1">Click + to start</p>
          </div>
        ) : (
          <div className="space-y-1 p-2">
            {conversations.map((conversation) => (
              <div
                key={conversation.id}
                onClick={() => handleSelectConversation(conversation.id)}
                className={`group flex items-center justify-between rounded-lg p-3 cursor-pointer transition-colors ${
                  currentConversation?.id === conversation.id
                    ? "bg-gray-800 text-white"
                    : "text-gray-400 hover:bg-gray-800 hover:text-white"
                }`}
              >
                <div className="flex-1 min-w-0">
                  <div className="truncate font-medium">{conversation.title}</div>
                  <div className="text-xs text-gray-500">
                    {conversation.message_count} messages
                  </div>
                </div>
                <button
                  onClick={(e) => handleDeleteConversation(conversation.id, e)}
                  className="opacity-0 group-hover:opacity-100 p-1 hover:bg-gray-700 rounded transition-opacity"
                  title="Delete conversation"
                >
                  <Trash2 className="h-4 w-4 text-red-400" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
