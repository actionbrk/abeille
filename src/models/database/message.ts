import { Message as DiscordMessage } from "discord.js";
import { HashHelper } from "../../utils/hash-helper";

export interface Message {
  message_id: number;
  author_id: string;
  channel_id: number;
  timestamp: Date;
  content: string | null;
  attachment_url: string | null;
}

export function fromDiscordMessage(message: DiscordMessage): Message {
  return {
    message_id: parseInt(message.id),
    channel_id: parseInt(message.channelId),
    author_id: HashHelper.computeHash(message.author.id),
    content: message.content,
    timestamp: new Date(message.createdTimestamp),
    attachment_url: message.attachments.size > 0 ? message.attachments.first()!.url : null,
  };
}
