import { getDbFolder, getLastMessageId } from "./database/bee-database";
import fs from "fs";
import logger from "./logger";

const cache = new Map<string, string>();

export function cacheLastEntriesOfDatabases(): void {
  const dbFolder = getDbFolder();

  const files = fs.readdirSync(dbFolder, { withFileTypes: true, recursive: true })

  files.forEach((file) => {
    if (file.isFile() && file.name.endsWith(".db")) {
      logger.info("Database file %s", file.name);

      const guildId = file.name.replace(/\.db$/, "");
      const lastMessageId = getLastMessageId(guildId);

      if (lastMessageId) {
        cache.set(guildId, lastMessageId);
      }
    }
  });
}

export function getLastMessageIdFromCache(guildId: string): string | undefined {
  return cache.get(guildId);
}

export function clearCache(): void {
  cache.clear();
}
