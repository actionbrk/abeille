import { InteractionContextType, MessageFlags, SlashCommandBuilder } from "discord.js";
import type { Command } from "../../models/command";
import { LocaleHelper } from "../../utils/locale-helper";
import { registerIdentity } from "../../database/bee-database";

const translations = LocaleHelper.getCommandTranslations("register");

const RegisterCommand: Command = {
  data: new SlashCommandBuilder()
    .setName("register")
    .setNameLocalizations(translations.localizedNames)
    .setDescription("Allow Abeille to store and display your username in rankings.")
    .setDescriptionLocalizations(translations.localizedDescriptions)
    .setContexts([InteractionContextType.Guild]),
  async execute(interaction) {
    const guildId = interaction.guildId!;
    const userId = interaction.user.id;

    registerIdentity(guildId, userId);

    await interaction.reply({
      content:
        translations.responses?.success?.[interaction.locale] ??
        "Your username will now be displayed in rankings. Use /unregister to remove it.",
      flags: [MessageFlags.Ephemeral],
    });
  },
};

export default RegisterCommand;
