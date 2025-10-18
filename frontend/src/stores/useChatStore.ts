/**
 * Zustand store for AI chat assistant state
 */

import { create } from "zustand";
import { chatAPI } from "@/lib/api";
import type { ChatConversation, ChatConversationListItem, ChatMessage } from "@/types";

interface ChatState {
  conversations: ChatConversationListItem[];
  currentConversation: ChatConversation | null;
  isStreaming: boolean;
  streamingMessage: string;
  isLoading: boolean;
  error: string | null;

  // Actions
  loadConversations: () => Promise<void>;
  selectConversation: (id: string) => Promise<void>;
  createNewConversation: (title?: string) => Promise<void>;
  sendMessage: (message: string) => Promise<void>;
  deleteConversation: (id: string) => Promise<void>;
  updateConversationTitle: (id: string, title: string) => Promise<void>;
  clearError: () => void;
  resetStreamingMessage: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  conversations: [],
  currentConversation: null,
  isStreaming: false,
  streamingMessage: "",
  isLoading: false,
  error: null,

  loadConversations: async () => {
    set({ isLoading: true, error: null });
    try {
      const conversations = await chatAPI.listConversations();
      set({ conversations, isLoading: false });
    } catch (error: any) {
      set({ error: error.message || "Failed to load conversations", isLoading: false });
      throw error;
    }
  },

  selectConversation: async (id: string) => {
    set({ isLoading: true, error: null });
    try {
      const conversation = await chatAPI.getConversation(id);
      set({ currentConversation: conversation, isLoading: false });
    } catch (error: any) {
      set({ error: error.message || "Failed to load conversation", isLoading: false });
      throw error;
    }
  },

  createNewConversation: async (title = "New Conversation") => {
    set({ isLoading: true, error: null });
    try {
      const conversation = await chatAPI.createConversation(title);
      set((state) => ({
        currentConversation: conversation,
        conversations: [
          {
            id: conversation.id,
            user_id: conversation.user_id,
            title: conversation.title,
            created_at: conversation.created_at,
            updated_at: conversation.updated_at,
            message_count: 0,
          },
          ...state.conversations,
        ],
        isLoading: false,
      }));
    } catch (error: any) {
      set({ error: error.message || "Failed to create conversation", isLoading: false });
      throw error;
    }
  },

  sendMessage: async (message: string) => {
    const { currentConversation } = get();
    if (!currentConversation) {
      set({ error: "No conversation selected" });
      return;
    }

    set({ isStreaming: true, streamingMessage: "", error: null });

    try {
      // Add user message to UI immediately
      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        conversation_id: currentConversation.id,
        role: "user",
        content: message,
        created_at: new Date().toISOString(),
      };

      set((state) => ({
        currentConversation: state.currentConversation
          ? {
              ...state.currentConversation,
              messages: [...(state.currentConversation.messages || []), userMessage],
            }
          : null,
      }));

      // Stream AI response
      chatAPI.streamMessage(
        currentConversation.id,
        message,
        (chunk: string) => {
          // On each chunk, append to streaming message
          set((state) => ({
            streamingMessage: state.streamingMessage + chunk,
          }));
        },
        () => {
          // On complete
          const { streamingMessage, currentConversation } = get();

          // Add assistant message to conversation
          const assistantMessage: ChatMessage = {
            id: crypto.randomUUID(),
            conversation_id: currentConversation!.id,
            role: "assistant",
            content: streamingMessage,
            created_at: new Date().toISOString(),
          };

          set((state) => ({
            currentConversation: state.currentConversation
              ? {
                  ...state.currentConversation,
                  messages: [...(state.currentConversation.messages || []), assistantMessage],
                }
              : null,
            isStreaming: false,
            streamingMessage: "",
          }));

          // Reload conversation to get actual message IDs from server
          get().selectConversation(currentConversation!.id);
        },
        (error: Error) => {
          // On error
          set({
            error: error.message || "Failed to send message",
            isStreaming: false,
            streamingMessage: "",
          });
        }
      );
    } catch (error: any) {
      set({
        error: error.message || "Failed to send message",
        isStreaming: false,
        streamingMessage: "",
      });
      throw error;
    }
  },

  deleteConversation: async (id: string) => {
    set({ isLoading: true, error: null });
    try {
      await chatAPI.deleteConversation(id);
      set((state) => ({
        conversations: state.conversations.filter((c) => c.id !== id),
        currentConversation: state.currentConversation?.id === id ? null : state.currentConversation,
        isLoading: false,
      }));
    } catch (error: any) {
      set({ error: error.message || "Failed to delete conversation", isLoading: false });
      throw error;
    }
  },

  updateConversationTitle: async (id: string, title: string) => {
    set({ isLoading: true, error: null });
    try {
      await chatAPI.updateConversation(id, title);
      set((state) => ({
        conversations: state.conversations.map((c) =>
          c.id === id ? { ...c, title } : c
        ),
        currentConversation:
          state.currentConversation?.id === id
            ? { ...state.currentConversation, title }
            : state.currentConversation,
        isLoading: false,
      }));
    } catch (error: any) {
      set({ error: error.message || "Failed to update conversation", isLoading: false });
      throw error;
    }
  },

  clearError: () => set({ error: null }),
  resetStreamingMessage: () => set({ streamingMessage: "" }),
}));
