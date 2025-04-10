import type { Translation } from "../models/translation";
import { Collection, Locale, type LocalizationMap } from "discord.js";
import { loadLocalesAsync } from "../loaders";
import logger from "../logger";

export type TranslationsMap = {
  localizedNames: LocalizationMap;
  localizedDescriptions: LocalizationMap;
  options?: { [optionName: string]: { localizedNames: LocalizationMap; localizedDescriptions: LocalizationMap } };
  responses?: { [responseName: string]: Record<string, string> };
};

export class LocaleHelper {
  static cachedLocales: Collection<Locale, Translation> = new Collection();
  static isInitialized = false;

  static async initLocalesAsync(): Promise<void> {
    const result = await loadLocalesAsync();
    this.cachedLocales = result;
    this.isInitialized = true;
    logger.info("Locales initialized successfully.");
  }

  private static ensureInitialized(): void {
    if (!this.isInitialized) {
      throw new Error("Locales not initialized. Please call initLocalesAsync() first.");
    }
  }

  static getCommandTranslations(commandName: string): TranslationsMap {
    this.ensureInitialized();

    const result: TranslationsMap = {
      localizedNames: {} as LocalizationMap,
      localizedDescriptions: {} as LocalizationMap,
    };

    this.cachedLocales.forEach((locale, localeKey) => {
      const command = locale.commands[commandName];
      if (command) {
        const { name, description, options } = command;
        result.localizedNames[localeKey] = name;
        result.localizedDescriptions[localeKey] = description;
        if (options) {
          result.options = result.options || {};
          Object.entries(options).forEach(([optionName, option]) => {
            result.options![optionName] = {
              localizedNames: { [localeKey]: option.name },
              localizedDescriptions: { [localeKey]: option.description },
            };
          });
        }
        if (command.responses) {
          result.responses = result.responses || {};
          Object.entries(command.responses).forEach(([responseName, response]) => {
            result.responses![responseName] ??= {};
            result.responses![responseName][localeKey] = response;
          });
        }
      } else {
        logger.error("Command %s not found in locale %s", commandName, localeKey);
      }
    });

    return result;
  }
}
