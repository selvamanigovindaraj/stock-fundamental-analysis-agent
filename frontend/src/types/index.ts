export interface Document {
  id: string;
  content: string;
  metadata: Record<string, string>;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: Document[];
}

export interface ChatResponse {
  message: string;
  sources: Document[];
  conversationId: string;
}
