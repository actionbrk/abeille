import { Database } from "bun:sqlite";
import type { Message } from "../models/database/message";
import type { TrendResult } from "../models/database/trend-result";
import type { RankResult } from "../models/database/rank-result";
import type { MessageDay } from "../models/database/message-day";
import { HashHelper } from "../utils/hash-helper";
import logger from "../logger";

const dbFolder = "./db";

export const getDbFolder = (): string => dbFolder;

export function saveMessage(guildId: string, message: Message) {
  const db = getDatabaseForGuild(guildId);

  db.transaction(() => {
    const statement = db.query(
      `INSERT INTO message (message_id, author_id, channel_id, timestamp, content, attachment_url)
       VALUES ($message_id, $author_id, $channel_id, $timestamp, $content, $attachment_url)`
    );

    statement.run({
      $message_id: message.message_id,
      $author_id: message.author_id,
      $channel_id: message.channel_id,
      $timestamp: message.timestamp.toISOString(),
      $content: message.content,
      $attachment_url: message.attachment_url,
    });

    // Atomic update of the daily message counter
    const date = new Date(message.timestamp).toISOString().split("T")[0];
    if (date) {
      const updateDayStatement = db.query(`
        INSERT INTO messageday (date, count)
        VALUES ($date, 1)
        ON CONFLICT(date) DO UPDATE SET
        count = count + 1
      `);
      updateDayStatement.run({ $date: date });
    }
  })();
}

export function updateMessage(
  guildId: string,
  message_id: string,
  content: string | null,
  attachment_url: string | null
) {
  const db = getDatabaseForGuild(guildId);
  const statement = db.query(
    `UPDATE message SET content=$content, attachment_url=$attachment_url WHERE message_id = $message_id`
  );

  statement.run({
    $message_id: message_id,
    $content: content,
    $attachment_url: attachment_url,
  });
}

export function deleteMessage(guildId: string, messageId: string) {
  const db = getDatabaseForGuild(guildId);
  const message = db
    .query(
      `SELECT message_id, author_id, channel_id, timestamp, content, attachment_url FROM message WHERE message_id = $message_id`
    )
    .get({ $message_id: messageId }) as Message | null;

  if (message) {
    const statement = db.query(`DELETE FROM message WHERE message_id = $message_id`);
    statement.run({
      $message_id: messageId,
    });

    updateMessageDay(guildId, message, true);
  }
}

export function getTrend(
  guildId: string,
  term: string
): { trend: TrendResult[]; guildFirstMessageDate: Date | null; guildLastMessageDate: Date | null } {
  const db = getDatabaseForGuild(guildId);
  const statement = db.query(`
    WITH matched AS (
      SELECT rowid
      FROM messageindex
      WHERE messageindex MATCH ?
    ),
    filtered_messages AS (
      SELECT m.*, DATE(m.timestamp) AS message_date
      FROM message m
      JOIN matched ON m.rowid = matched.rowid
    )
    SELECT fm.message_date AS date,
           COUNT(*) / CAST(md.count AS REAL) AS messages
    FROM filtered_messages fm
    JOIN messageday md ON fm.message_date = md.date
    GROUP BY fm.message_date
    ORDER BY fm.message_date;
  `);

  const firstDate = db.query(`SELECT date FROM messageday ORDER BY date ASC LIMIT 1`);
  const lastDate = db.query(`SELECT date FROM messageday ORDER BY date DESC LIMIT 1`);

  const trend = statement.all(`"${term}"`) as TrendResult[];
  const guildFirstMessageDate = firstDate.get() as { date: string } | null;
  const guildLastMessageDate = lastDate.get() as { date: string } | null;

  return {
    trend,
    guildFirstMessageDate: guildFirstMessageDate !== null ? new Date(Date.parse(guildFirstMessageDate.date)) : null,
    guildLastMessageDate: guildLastMessageDate !== null ? new Date(Date.parse(guildLastMessageDate.date)) : null,
  };
}

export function getRank(guildId: string, expression: string): RankResult[] {
  const db = getDatabaseForGuild(guildId);
  const statement = db.query(`
    WITH matched AS (
      SELECT rowid
      FROM messageindex
      WHERE messageindex MATCH ?
    )
    SELECT IF (i.real_author_id IS NULL, m.author_id, CAST(i.real_author_id AS TEXT)) as author_id,
           COUNT(*) AS count
    FROM matched
    JOIN message AS m ON m.rowid = matched.rowid
    LEFT JOIN "identity" i ON m.author_id = i.author_id
    GROUP BY m.author_id
    ORDER BY count DESC;
  `);

  return statement.all(`"${expression}"`) as RankResult[];
}

export interface RandomMessageOptions {
  channelId?: string;
  media?: boolean;
  minLength?: number;
  authorId?: string;
}

export function getRandomMessage(guildId: string, options: RandomMessageOptions): Message | null {
  const db = getDatabaseForGuild(guildId);
  let query = `
    WITH filtered_messages AS (
      SELECT message_id, author_id, channel_id, timestamp, content, attachment_url
      FROM message
      WHERE 1=1
  `;

  const params: string[] = [];

  if (options.channelId) {
    query += " AND channel_id = ?";
    params.push(options.channelId.toString());
  }

  if (options.media) {
    query += " AND attachment_url IS NOT NULL";
  }

  if (options.minLength) {
    query += " AND length(content) > ?";
    params.push(options.minLength.toString());
  }

  if (options.authorId) {
    query += " AND author_id = ?";
    params.push(HashHelper.computeHash(options.authorId));
  }

  query += `)
    SELECT message_id, author_id, channel_id, timestamp, content, attachment_url
    FROM filtered_messages
    ORDER BY RANDOM()
    LIMIT 1;
  `;

  const statement = db.query(query);
  return statement.get(...params) as Message | null;
}

export function registerIdentity(guildId: string, userId: string): void {
  const db = getDatabaseForGuild(guildId);
  const hashedId = HashHelper.computeHash(userId);
  const statement = db.query(
    "INSERT OR REPLACE INTO identity (author_id, real_author_id) VALUES ($author_id, $real_author_id)"
  );
  statement.run({
    $author_id: hashedId,
    $real_author_id: userId,
  });
}

export function unregisterIdentity(guildId: string, userId: string): void {
  const db = getDatabaseForGuild(guildId);
  const hashedId = HashHelper.computeHash(userId);
  const statement = db.query("DELETE FROM identity WHERE author_id = $author_id");
  statement.run({
    $author_id: hashedId,
  });
}

export function exportUserMessages(guildId: string, userId: string): Message[] {
  const db = getDatabaseForGuild(guildId);
  const hashedId = HashHelper.computeHash(userId);
  const statement = db.query(
    "SELECT message_id, author_id, channel_id, timestamp, content, attachment_url FROM message WHERE author_id = $author_id ORDER BY timestamp"
  );
  return statement.all({
    $author_id: hashedId,
  }) as Message[];
}

export function deleteUserMessage(guildId: string, userId: string, messageId: string): boolean {
  const db = getDatabaseForGuild(guildId);
  const hashedId = HashHelper.computeHash(userId);
  const message = db
    .query(
      "SELECT message_id, author_id, channel_id, timestamp, content, attachment_url FROM message WHERE message_id = $message_id AND author_id = $author_id"
    )
    .get({
      $message_id: messageId,
      $author_id: hashedId,
    }) as Message | null;

  if (message) {
    const statement = db.query("DELETE FROM message WHERE message_id = $message_id AND author_id = $author_id");
    const result = statement.run({
      $message_id: messageId,
      $author_id: hashedId,
    });

    updateMessageDay(guildId, message, true);
    return result.changes > 0;
  }

  return false;
}

export interface ChannelStats {
  count: number;
  firstMessage: Date;
  lastMessage: Date;
}

export function getChannelStats(guildId: string): Map<string, ChannelStats> {
  const db = getDatabaseForGuild(guildId);
  const statement = db.query(`
    SELECT
      channel_id,
      COUNT(*) as count,
      MIN(timestamp) as first_message,
      MAX(timestamp) as last_message
    FROM message
    GROUP BY channel_id
  `);

  const results = statement.all() as {
    channel_id: string;
    count: number;
    first_message: string;
    last_message: string;
  }[];
  const statsMap = new Map<string, ChannelStats>();

  results.forEach((row) => {
    statsMap.set(row.channel_id, {
      count: row.count,
      firstMessage: new Date(row.first_message),
      lastMessage: new Date(row.last_message),
    });
  });

  return statsMap;
}

export function purgeDeletedMessages(guildId: string, messageIds: string[]): number {
  const db = getDatabaseForGuild(guildId);
  const messages = db
    .query(
      "SELECT message_id, author_id, channel_id, timestamp, content, attachment_url FROM message WHERE message_id IN ($messageIds)"
    )
    .all({
      $messageIds: messageIds.join(","),
    }) as Message[];

  const statement = db.query("DELETE FROM message WHERE message_id IN ($messageIds)");
  const result = statement.run({
    $messageIds: messageIds.join(","),
  });

  messages.forEach((message) => updateMessageDay(guildId, message, true));
  return result.changes;
}

export async function saveChannelMessages(guildId: string, messages: Message[]): Promise<void> {
  const db = getDatabaseForGuild(guildId);

  db.transaction(() => {
    const insertStatement = db.query(
      "INSERT OR IGNORE INTO message (message_id, author_id, channel_id, timestamp, content, attachment_url) VALUES ($message_id, $author_id, $channel_id, $timestamp, $content, $attachment_url)"
    );

    // Group messages by date for counter updates
    const messagesByDate = new Map<string, number>();

    for (const message of messages) {
      insertStatement.run({
        $message_id: message.message_id,
        $author_id: message.author_id,
        $channel_id: message.channel_id,
        $timestamp: message.timestamp.toISOString(),
        $content: message.content,
        $attachment_url: message.attachment_url,
      });

      const date = new Date(message.timestamp).toISOString().split("T")[0];
      if (date) {
        messagesByDate.set(date, (messagesByDate.get(date) || 0) + 1);
      }
    }

    // Update daily counters in a single transaction
    for (const [date, count] of messagesByDate) {
      const updateDayStatement = db.query(`
        INSERT INTO messageday (date, count)
        VALUES ($date, $count)
        ON CONFLICT(date) DO UPDATE SET
        count = count + $count
      `);
      updateDayStatement.run({
        $date: date,
        $count: count,
      });
    }
  })();
}

export async function optimizeDatabase(guildId: string): Promise<void> {
  const db = getDatabaseForGuild(guildId);

  // Run VACUUM to reclaim space and defragment
  db.exec("VACUUM;");

  // Analyze tables to update statistics
  db.exec("ANALYZE;");

  // Optimize FTS5 tables
  try {
    logger.info("Optimizing FTS5 index for messageindex...");
    db.exec("INSERT INTO messageindex(messageindex) VALUES('optimize');");
    logger.info("FTS5 index for messageindex optimized successfully.");
  } catch (error) {
    logger.error("Failed to optimize FTS5 table 'messageindex':", error);
  }
}

export async function rebuildIndexes(guildId: string): Promise<void> {
  const db = getDatabaseForGuild(guildId);

  // Rebuild the FTS5 index
  try {
    logger.info("Rebuilding FTS5 index for messageindex...");
    db.exec("INSERT INTO messageindex(messageindex) VALUES('rebuild');");
    logger.info("FTS5 index for messageindex rebuilt successfully.");
    await optimizeDatabase(guildId);
  } catch (error) {
    logger.error("Failed to rebuild FTS5 table 'messageindex':", error);
  }
}

export function updateMessageDay(guildId: string, message: Message, isDelete: boolean = false): void {
  const db = getDatabaseForGuild(guildId);
  const date = new Date(message.timestamp).toISOString().split("T")[0];
  if (!date) return;

  db.transaction(() => {
    // First check if the entry exists
    const checkStatement = db.query(`
      SELECT count FROM messageday WHERE date = $date
    `);
    const result = checkStatement.get({ $date: date }) as { count: number } | undefined;

    if (result) {
      // Atomic update with check to prevent negative counter
      const updateStatement = db.query(`
        UPDATE messageday
        SET count = MAX(0, count ${isDelete ? "-" : "+"} 1)
        WHERE date = $date
      `);
      updateStatement.run({ $date: date });
    } else if (!isDelete) {
      // Insert only if it's not a deletion
      const insertStatement = db.query(`
        INSERT INTO messageday (date, count)
        VALUES ($date, 1)
      `);
      insertStatement.run({ $date: date });
    }
  })();
}

export function getMessageDayRange(guildId: string, startDate: Date, endDate: Date): MessageDay[] {
  const db = getDatabaseForGuild(guildId);
  const statement = db.query(`
    SELECT date, count
    FROM messageday
    WHERE date BETWEEN $startDate AND $endDate
    ORDER BY date
  `);

  const startDateStr = startDate.toISOString().split("T")[0];
  const endDateStr = endDate.toISOString().split("T")[0];
  if (!startDateStr || !endDateStr) return [];

  return statement.all({
    $startDate: startDateStr,
    $endDate: endDateStr,
  }) as MessageDay[];
}

export function initializeMessageDays(guildId: string) {
  const db = getDatabaseForGuild(guildId);

  // Get the range of dates from messages
  const dateRange = db
    .query(
      `
    SELECT
      MIN(DATE(timestamp)) as min_date,
      MAX(DATE(timestamp)) as max_date
    FROM message
  `
    )
    .get() as { min_date: string; max_date: string };

  if (!dateRange.min_date || !dateRange.max_date) {
    return;
  }

  db.transaction(() => {
    // Clear existing data
    db.run(`DELETE FROM messageday`);

    // Calculate daily counts
    db.run(`
      INSERT INTO messageday (date, count)
      SELECT
        DATE(timestamp) as date,
        COUNT(*) as count
      FROM message
      GROUP BY DATE(timestamp)
    `);
  })();
}

export function cleanOldChannels(guildId: string, channelIds: string[]): void {
  const db = getDatabaseForGuild(guildId);

  const existingChannels = db.query("SELECT DISTINCT channel_id FROM message").all() as { channel_id: string }[];
  const channelsToDelete = existingChannels
    .map((c) => c.channel_id)
    .filter((channelId) => !channelIds.includes(channelId));

  const batchSize = 500;
  // Process channels to delete in batches to avoid sqlite's limit on the number of parameters
  db.transaction(() => {
    for (let i = 0; i < channelsToDelete.length; i += batchSize) {
      const batch = channelsToDelete.slice(i, i + batchSize);
      const placeholders = batch.map(() => "?").join(",");
      const statement = db.query(`DELETE FROM message WHERE channel_id IN (${placeholders})`);
      statement.run(...batch);
    }
  })();
}

export function deleteMessagesFromChannel(guildId: string, channelId: string): void {
  const db = getDatabaseForGuild(guildId);
  const statement = db.query(`DELETE FROM message WHERE channel_id = ?`);
  statement.run(channelId);
}

export function getLastMessageId(guildId: string): string | null {
  const db = getDatabaseForGuild(guildId);
  const statement = db.query(`SELECT message_id FROM message ORDER BY timestamp DESC LIMIT 1`);
  const result = statement.get() as { message_id: string } | null;
  return result ? result.message_id : null;
}

const existingDatabases = new Set<string>();

const getDatabaseForGuild = (guildId: string): Database => {
  const dbPath = `${dbFolder}/${guildId}.db`;
  const db = new Database(dbPath);

  if (!existingDatabases.has(guildId)) {
    existingDatabases.add(guildId);
    initDatabase(db);
    initializeMessageDays(guildId);
  }

  return db;
};

function initDatabase(db: Database) {
  db.exec(`
    CREATE TABLE IF NOT EXISTS message (
      message_id TEXT PRIMARY KEY,
      author_id TEXT NOT NULL,
      channel_id TEXT NOT NULL,
      timestamp TEXT NOT NULL,
      content TEXT,
      attachment_url TEXT
    );

    CREATE TABLE IF NOT EXISTS identity (
      author_id TEXT PRIMARY KEY,
      real_author_id TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS messageday (
      date TEXT PRIMARY KEY,
      count INTEGER NOT NULL
    );

    CREATE VIRTUAL TABLE IF NOT EXISTS "messageindex" USING fts5 ("content", content="message", tokenize="trigram");
  `);

  db.exec(
    `CREATE TRIGGER IF NOT EXISTS message_ad AFTER DELETE ON message BEGIN INSERT INTO messageindex(messageindex, rowid, content) VALUES('delete', old.rowid, old.content); END;`
  );
  db.exec(
    `CREATE TRIGGER IF NOT EXISTS message_ai AFTER INSERT ON message BEGIN INSERT INTO messageindex(rowid, content) VALUES (new.rowid, new.content); END;`
  );
  db.exec(
    `CREATE TRIGGER IF NOT EXISTS message_au AFTER UPDATE ON message BEGIN INSERT INTO messageindex(messageindex, rowid, content) VALUES('delete', old.rowid, old.content); INSERT INTO messageindex(rowid, content) VALUES (new.rowid, new.content); END;`
  );
}
