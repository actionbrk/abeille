const DISCORD_EPOCH = BigInt(1420070400000); // 2015-01-01T00:00:00.000Z

export function getSnowflakeFromDate(date: Date = new Date()): string {
    const now = (BigInt(date.valueOf()) - DISCORD_EPOCH) << BigInt(22);
    return now.toString();
}