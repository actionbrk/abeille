import { MessageType, type Message as DiscordMessage } from "discord.js";
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

export function filterSaveMessages(message: Message, discordMessage: DiscordMessage): boolean {
  return (
    ((message.content !== null && message.content.trim() !== "") || message.attachment_url !== null) &&
    // When a thread is created inside a text channel, it sends a message with the type ThreadCreated.
    // We don't want to save that message, because it will duplicate the message from the text channel.
    discordMessage.type !== MessageType.ThreadCreated
  );
}
