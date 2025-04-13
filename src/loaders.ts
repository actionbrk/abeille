import path from "path";
import fs from "fs";
import logger from "./logger";
import { Client, Collection, Locale } from "discord.js";
import type { BeeEvent } from "./models/events";
import type { Command } from "./models/command";
import type { Translation } from "./models/translation";
import fsPromises from "fs/promises";

async function loadFileAsync(filePath: string): Promise<Command | null> {
  try {
    const command = (await import(filePath)).default as Command;
    return command;
  } catch (error) {
    logger.error("Error loading command %s: %o", filePath, error);
    return null;
  }
}

async function loadDirectoryAsync(dirPath: string): Promise<Command[]> {
  const files = await fsPromises.readdir(dirPath);
  const commands: Command[] = [];

  for (const file of files) {
    const filePath = path.join(dirPath, file);
    const stat = await fsPromises.stat(filePath);

    if (stat.isDirectory()) {
      const subCommands = await loadDirectoryAsync(filePath);
      commands.push(...subCommands);
    } else if (file.endsWith(".ts") || file.endsWith(".js")) {
      const command = await loadFileAsync(filePath);
      if (command) {
        commands.push(command);
      }
    }
  }

  return commands;
}

export async function loadEventsAsync(client: Client) {
  const eventsPath = path.join(__dirname, "events");
  const eventFiles = getTsFilesRecursive(eventsPath);

  for (const file of eventFiles) {
    const defaultExport = await import(file);

    if (defaultExport.default) {
      const event: BeeEvent = defaultExport.default;
      if (event.once) {
        logger.info("Loading event: %s (once)", event.name);
        client.once(event.name, (...args) => event.execute(...args));
      } else {
        logger.info("Loading event: %s", event.name);
        client.on(event.name, (...args) => event.execute(...args));
      }
    } else {
      logger.error("Event file %s does not have a default export.", file);
    }
  }
}

export async function loadCommandsAsync(): Promise<Collection<string, Command>> {
  const commands = new Collection<string, Command>();
  const commandsPath = path.join(__dirname, "commands");
  const loadedCommands = await loadDirectoryAsync(commandsPath);

  for (const command of loadedCommands) {
    if ("data" in command && "execute" in command) {
      commands.set(command.data.name, command);
      logger.debug("Loaded command: %s", command.data.name);
    } else {
      logger.warn("Command at %s is missing required properties.", command);
    }
  }

  return commands;
}

export async function loadLocalesAsync() {
  const localesPath = path.join(__dirname, "locales");
  const localeFiles = fs.readdirSync(localesPath).filter((file) => file.endsWith(".json"));

  const locales = new Collection<Locale, Translation>();

  const possibleLocales = Object.values(Locale);

  for (const file of localeFiles) {
    const filePath = path.join(localesPath, file);
    const localeName = file.split(".")[0];
    const localeData = JSON.parse(fs.readFileSync(filePath, "utf-8"));

    if (!possibleLocales.includes(localeName as Locale)) {
      logger.error("Locale '%s' is not a valid locale. Verify names of files in locales folder.", localeName);
      process.exit(1);
    }

    locales.set(localeName! as Locale, localeData);
  }

  return locales;
}

function getTsFilesRecursive(commandsPath: string) {
  return fs
    .readdirSync(commandsPath, { withFileTypes: true, recursive: true })
    .map((dirent) => {
      if (dirent.isFile()) {
        const file = dirent.name;
        if (file.endsWith(".ts")) {
          return path.join(dirent.parentPath, dirent.name);
        } else {
          return null;
        }
      } else {
        return null;
      }
    })
    .filter((file) => file !== null);
}
