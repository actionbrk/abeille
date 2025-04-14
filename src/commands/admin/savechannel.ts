import { ChannelType, InteractionContextType, PermissionFlagsBits, SlashCommandBuilder } from "discord.js";
import type { Command } from "../../models/command";
import { LocaleHelper } from "../../utils/locale-helper";
import { saveMessagesForGuild } from "./save";

const translations = LocaleHelper.getCommandTranslations("savechannel");

const SaveChannelCommand: Command = {
  data: new SlashCommandBuilder()
    .setName("savechannel")
    .setNameLocalizations(translations.localizedNames)
    .setDescription("Force save messages from a specific channel.")
    .setDescriptionLocalizations(translations.localizedDescriptions)
    .setContexts([InteractionContextType.Guild])
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator)
    .addChannelOption((option) =>
      option
        .setName("channel")
        .setNameLocalizations(translations.options!.channel!.localizedNames)
        .setDescription("Channel to save messages from.")
        .setDescriptionLocalizations(translations.options!.channel!.localizedDescriptions)
        .addChannelTypes(ChannelType.GuildText)
        .setRequired(true)
    ),
  async execute(interaction) {
    await interaction.deferReply();

    const channel = interaction.options.getChannel("channel", true, [ChannelType.GuildText]);

    if (!channel.isTextBased()) {
      await interaction.editReply({
        content: translations.responses?.invalidChannel?.[interaction.locale] ?? "Only text channels can be saved.",
      });
      return;
    }

    await saveMessagesForGuild(interaction.guild!, undefined, interaction, channel.id);
  },
};

export default SaveChannelCommand;
