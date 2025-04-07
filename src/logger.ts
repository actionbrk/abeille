import { createLogger, format, transports } from "winston";

const logger = createLogger({
  level: "info",
  format: format.combine(
    format.timestamp(),
    format.colorize(),
    format.splat(),
    format.align(),
    format.printf(({ level, message, timestamp }) => `${timestamp} ${level} ${message}`)
  ),
  transports: [new transports.Console()],
});

export default logger;
