import type { Message as DiscordMessage } from "discord.js";
import { HashHelper } from "../../utils/hash-helper";

export interface Message {
  message_id: string;
  author_id: string;
  channel_id: string;
  timestamp: Date;
  content: string | null;
  attachment_url: string | null;
}

export function fromDiscordMessage(message: DiscordMessage): Message {
  return {
    message_id: message.id,
    author_id: HashHelper.computeHash(message.author.id),
    channel_id: message.channelId,
    timestamp: message.createdAt,
    content: message.content || null,
    attachment_url: message.attachments.first()?.url || null,
  };
}
