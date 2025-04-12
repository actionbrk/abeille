import { InteractionContextType, MessageFlags, SlashCommandBuilder } from "discord.js";
import type { Command } from "../../models/command";
import { LocaleHelper } from "../../utils/locale-helper";
import { unregisterIdentity } from "../../database/bee-database";

const translations = LocaleHelper.getCommandTranslations("unregister");

const UnregisterCommand: Command = {
  data: new SlashCommandBuilder()
    .setName("unregister")
    .setNameLocalizations(translations.localizedNames)
    .setDescription("Remove your username from Abeille's storage.")
    .setDescriptionLocalizations(translations.localizedDescriptions)
    .setContexts([InteractionContextType.Guild]),
  async execute(interaction) {
    const guildId = interaction.guildId!;
    const userId = interaction.user.id;

    unregisterIdentity(guildId, userId);

    await interaction.reply({
      content:
        translations.responses?.success?.[interaction.locale] ??
        "Your username has been removed from storage. Use /register to allow it again.",
      flags: [MessageFlags.Ephemeral],
    });
  },
};

export default UnregisterCommand;
