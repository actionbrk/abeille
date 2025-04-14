import { type ThreadManager, Collection, type GuildBasedChannel, type TextBasedChannel, ChannelType } from "discord.js";
import logger from "../logger";

export async function getAllTextChannels(
  viewableChannels: Collection<string, GuildBasedChannel>
): Promise<Collection<string, GuildBasedChannel & TextBasedChannel>> {
  const textChannels = new Collection<string, GuildBasedChannel & TextBasedChannel>();

  for (const [, channel] of viewableChannels) {
    if (channel.isTextBased()) {
      textChannels.set(channel.id, channel);
      if (channel.type === ChannelType.GuildText) {
        await fetchAndStoreThreads(channel.threads, textChannels);
      }
    } else {
      switch (channel.type) {
        case ChannelType.GuildForum:
        case ChannelType.GuildMedia: {
          await fetchAndStoreThreads(channel.threads, textChannels);
          break;
        }
        case ChannelType.GuildCategory:
          break;
        default:
          logger.warn("Unknown channel %o", channel);
          break;
      }
    }
  }

  return textChannels;
}

/**
 * Fetches and stores threads from a given thread manager into a collection.
 * @param {ThreadManager} threadManager - The thread manager to fetch threads from.
 * @param {Collection<string, GuildBasedChannel & TextBasedChannel>} textChannels - The collection to store the threads in.
 */
async function fetchAndStoreThreads(
  threadManager: ThreadManager,
  textChannels: Collection<string, GuildBasedChannel & TextBasedChannel>
): Promise<void> {
  const activeChannelThreads = await threadManager.fetchActive(true);
  activeChannelThreads.threads.forEach((thread) => {
    textChannels.set(thread.id, thread);
  });

  const publicArchivedChannelThreads = await threadManager.fetchArchived({ fetchAll: true, type: "public" }, false);
  publicArchivedChannelThreads.threads.forEach((thread) => {
    textChannels.set(thread.id, thread);
  });

  const privateArchivedChannelThreads = await threadManager.fetchArchived({ fetchAll: true, type: "private" }, false);
  privateArchivedChannelThreads.threads.forEach((thread) => {
    textChannels.set(thread.id, thread);
  });
}
