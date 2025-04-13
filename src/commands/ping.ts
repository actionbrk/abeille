import { InteractionContextType, MessageFlags, SlashCommandBuilder } from "discord.js";
import type { Command } from "../models/command";
import { LocaleHelper } from "../utils/locale-helper";

const translations = LocaleHelper.getCommandTranslations("ping");

const PingCommand: Command = {
  data: new SlashCommandBuilder()
    .setName("ping")
    .setNameLocalizations(translations.localizedNames)
    .setDescription("Ping the bot")
    .setDescriptionLocalizations(translations.localizedDescriptions)
    .setContexts([InteractionContextType.Guild]),
  async execute(interaction) {
    interaction.reply({
      content: "Pong!",
      flags: [MessageFlags.Ephemeral],
    });
  },
};

export default PingCommand;
