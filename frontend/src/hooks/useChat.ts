import type { ChatMessage } from "../types";

export function useChat(): {
  messages: ChatMessage[];
  sendMessage: (message: string) => Promise<void>;
} {
  // TODO: implement
  throw new Error("Not implemented");
}
