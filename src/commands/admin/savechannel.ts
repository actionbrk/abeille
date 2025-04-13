import { ChannelType, InteractionContextType, PermissionFlagsBits, SlashCommandBuilder } from "discord.js";
import type { Command } from "../../models/command";
import { LocaleHelper } from "../../utils/locale-helper";
import { initializeMessageDays, optimizeDatabase, saveChannelMessages } from "../../database/bee-database";
import { fromDiscordMessage, messageHasContentOrUrl } from "../../models/database/message";
import logger from "../../logger";

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

    const guildId = interaction.guildId!;
    const channel = interaction.options.getChannel("channel", true, [ChannelType.GuildText]);

    if (!channel.isTextBased()) {
      await interaction.editReply({
        content: translations.responses?.invalidChannel?.[interaction.locale] ?? "Only text channels can be saved.",
      });
      return;
    }

    let totalSaved = 0;
    const channelMessages = [];

    const progressMessage = await interaction.editReply({
      content: (
        translations.responses?.scanning?.[interaction.locale] ?? "Scanning messages from #{channel}..."
      ).replace("{channel}", channel.name ?? ""),
    });

    try {
      let lastMessageId: string | undefined;
      let messagesFound = true;

      // Fetch messages in batches
      while (messagesFound) {
        const options = { limit: 100 } as { limit: number; before?: string };
        if (lastMessageId) {
          options.before = lastMessageId;
        }

        const messages = await channel.messages.fetch(options);
        if (messages.size === 0) {
          messagesFound = false;
          continue;
        }

        // Convert messages to our format
        const validMessages = messages
          .filter((msg) => !msg.author.bot)
          .map((msg) => fromDiscordMessage(msg))
          .filter((msg) => messageHasContentOrUrl(msg));

        channelMessages.push(...validMessages);

        // Update progress
        totalSaved += validMessages.length;
        await progressMessage.edit({
          content: (
            translations.responses?.progress?.[interaction.locale] ?? "Saved {saved} messages from #{channel}..."
          )
            .replace("{saved}", totalSaved.toString())
            .replace("{channel}", channel.name),
        });

        lastMessageId = messages.last()?.id;
      }

      if (channelMessages.length > 0) {
        await saveChannelMessages(guildId, channelMessages);
      }

      initializeMessageDays(guildId);
      await optimizeDatabase(guildId);

      await progressMessage.edit({
        content: (
          translations.responses?.success?.[interaction.locale] ??
          "Successfully saved {messages} messages from #{channel}."
        )
          .replace("{messages}", totalSaved.toString())
          .replace("{channel}", channel.name),
      });
    } catch (error) {
      logger.error("Error saving channel %s: %o", channel.id, error);
      await progressMessage.edit({
        content: (
          translations.responses?.error?.[interaction.locale] ??
          "An error occurred while saving messages from #{channel}."
        ).replace("{channel}", channel.name),
      });
    }
  },
};

export default SaveChannelCommand;
