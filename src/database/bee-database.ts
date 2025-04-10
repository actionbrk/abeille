import { Database } from "bun:sqlite";
import type { Message } from "../models/database/message";
import { TrendResult } from "../models/database/trend-result";
import { RankResult } from "../models/database/rank-result";

export function saveMessage(guildId: string, message: Message) {
  const db = getDatabaseForGuild(guildId);
  const statement = db.query(
    `INSERT INTO message (message_id, author_id, channel_id, timestamp, content, attachment_url) VALUES ($message_id, $author_id, $channel_id, $timestamp, $content, $attachment_url)`
  );

  statement.run({
    $message_id: message.message_id,
    $author_id: message.author_id,
    $channel_id: message.channel_id,
    $timestamp: message.timestamp.toISOString(),
    $content: message.content,
    $attachment_url: message.attachment_url,
  });
}

export function updateMessage(guildId: string, message: Message) {
  const db = getDatabaseForGuild(guildId);
  const statement = db.query(
    `UPDATE message SET content=$content, attachment_url=$attachment_url WHERE message_id = $message_id`
  );

  statement.run({
    message_id: message.message_id,
    content: message.content,
    attachment_url: message.attachment_url,
  });
}

export function deleteMessage(guildId: string, messageId: number) {
  const db = getDatabaseForGuild(guildId);
  const statement = db.query(`DELETE FROM message WHERE message_id = $message_id`);
  statement.run({
    message_id: messageId,
  });
}

export function getTrend(
  guildId: string,
  term: string
): { trend: TrendResult[]; guildFirstMessageDate: Date | null; guildLastMessageDate: Date | null } {
  const db = getDatabaseForGuild(guildId);
  const statement = db
    .query(
      `WITH matched AS (
    SELECT rowid
    FROM messageindex
    WHERE messageindex MATCH $term
),
filtered_messages AS (
    SELECT m.*, DATE(m.timestamp) AS message_date
    FROM message m
    JOIN matched ON m.message_id = matched.rowid
)
SELECT fm.message_date AS date,
       COUNT(*) / CAST(md.count AS REAL) AS messages
FROM filtered_messages fm
JOIN messageday md ON fm.message_date = md.date
GROUP BY fm.message_date
ORDER BY fm.message_date;`
    )
    .as(TrendResult);

  const firstDate = db.query(`SELECT date FROM messageday LIMIT 1`);
  const lastDate = db.query(`SELECT date FROM messageday ORDER BY date desc LIMIT 1`);

  const trend = statement.all({ $term: `"${term}"` });
  const guildFirstMessageDate: { date: string } | null = firstDate.get("date") as { date: string } | null;
  const guildLastMessageDate: { date: string } | null = lastDate.get("date") as { date: string } | null;

  return {
    trend,
    guildFirstMessageDate: guildFirstMessageDate !== null ? new Date(Date.parse(guildFirstMessageDate.date)) : null,
    guildLastMessageDate: guildLastMessageDate !== null ? new Date(Date.parse(guildLastMessageDate.date)) : null,
  };
}

export function getRank(guildId: string, expression: string): RankResult[] {
  const db = getDatabaseForGuild(guildId);

  const statement = db
    .query(
      `WITH matched AS (
    SELECT rowid
    FROM messageindex
    WHERE messageindex MATCH $expression
)
SELECT IF (i.real_author_id IS NULL, m.author_id, CAST(i.real_author_id AS TEXT)) as author_id, COUNT(*) AS count
FROM matched
JOIN message AS m ON m.message_id = matched.rowid
LEFT JOIN "identity" i ON m.author_id = i.author_id
GROUP BY m.author_id
ORDER BY count DESC;`
    )
    .as(RankResult);

  const result = statement.all({ $expression: expression });
  return result;
}

const existingDatabases = new Set<string>();

const getDatabaseForGuild = (guildId: string): Database => {
  const dbPath = `./db/${guildId}.db`;
  const db = new Database(dbPath);

  if (!existingDatabases.has(guildId)) {
    existingDatabases.add(guildId);
    initDatabase(db);
  }

  return db;
};

function initDatabase(db: Database) {
  db.exec(`
    CREATE TABLE IF NOT EXISTS message (
      message_id INTEGER PRIMARY KEY,
      author_id TEXT NOT NULL,
      channel_id INTEGER NOT NULL,
      timestamp TEXT NOT NULL,
      content TEXT,
      attachment_url TEXT
    );

    CREATE TABLE IF NOT EXISTS identity (
      author_id TEXT PRIMARY KEY,
      real_author_id INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS messageday (
      date TEXT PRIMARY KEY,
      count INTEGER NOT NULL
    );

    CREATE VIRTUAL TABLE IF NOT EXISTS "messageindex" USING fts5 ("content", content="message", content_rowid="message_id", tokenize="trigram");
  `);

  db.exec(
    `CREATE TRIGGER IF NOT EXISTS message_ad AFTER DELETE ON message BEGIN INSERT INTO messageindex(messageindex, rowid, content) VALUES('delete', old.message_id, old.content); END;`
  );
  db.exec(
    `CREATE TRIGGER IF NOT EXISTS message_ai AFTER INSERT ON message BEGIN INSERT INTO messageindex(rowid, content) VALUES (new.message_id, new.content); END;`
  );
  db.exec(
    `CREATE TRIGGER IF NOT EXISTS message_au AFTER UPDATE ON message BEGIN INSERT INTO messageindex(messageindex, rowid, content) VALUES('delete', old.message_id, old.content); INSERT INTO messageindex(rowid, content) VALUES (new.message_id, new.content); END;`
  );
}
