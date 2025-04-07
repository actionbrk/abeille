import path from "path";
import fs from "fs";
import logger from "./logger";
import { Client, Collection, Locale } from "discord.js";
import type { BeeEvent } from "./models/events";
import type { Command } from "./models/command";
import type { Translation } from "./models/translation";

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
  const commandsPath = path.join(__dirname, "commands");
  const commandFiles = getTsFilesRecursive(commandsPath);

  const commands = new Collection<string, Command>();

  for (const file of commandFiles) {
    const defaultExport = await import(file);

    if (defaultExport.default) {
      const command: Command = defaultExport.default;
      logger.info("Loading command: %s", command.data.name);
      commands.set(command.data.name, command);
    } else {
      logger.error("Command file %s does not have a default export.", file);
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
