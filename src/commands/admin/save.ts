import {
  InteractionContextType,
  PermissionFlagsBits,
  SlashCommandBuilder,
  type FetchMessagesOptions,
} from "discord.js";
import type { Command } from "../../models/command";
import { LocaleHelper } from "../../utils/locale-helper";
import {
  cleanOldChannels,
  initializeMessageDays,
  optimizeDatabase,
  saveChannelMessages,
} from "../../database/bee-database";
import { fromDiscordMessage } from "../../models/database/message";
import logger from "../../logger";

const translations = LocaleHelper.getCommandTranslations("save");

const SaveCommand: Command = {
  data: new SlashCommandBuilder()
    .setName("save")
    .setNameLocalizations(translations.localizedNames)
    .setDescription("Force a complete save of all messages.")
    .setDescriptionLocalizations(translations.localizedDescriptions)
    .setContexts([InteractionContextType.Guild])
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),
  async execute(interaction) {
    await interaction.deferReply();

    const guildId = interaction.guildId!;
    const guild = interaction.guild!;

    let totalSaved = 0;
    let totalChannels = 0;

    // Get all text channels
    const textChannels = guild.channels.cache.filter((channel) => channel.viewable);

    const progressMessage = await interaction.editReply({
      content: translations.responses?.scanning?.[interaction.locale] ?? "Scanning channels for messages...",
    });

    // Process each channel
    for (const [, channel] of textChannels) {
      try {
        let lastMessageId: string | undefined;
        let messagesFound = true;
        const channelMessages = [];

        // Fetch messages in batches
        while (messagesFound) {
          if (!channel.isTextBased()) {
            logger.warn("Skipping non-text channel %s", channel.name);
            messagesFound = false;
            continue;
          }

          const options: FetchMessagesOptions = { limit: 100, cache: false };
          if (lastMessageId) {
            options.before = lastMessageId;
          }
          const messages = await channel.messages.fetch(options);
          if (messages.size === 0) {
            messagesFound = false;
            if (lastMessageId) {
              logger.info("No more messages found in channel %s", channel.name);
            } else {
              logger.info("No messages found in channel %s", channel.name);
            }
            continue;
          } else {
            logger.info("Fetched %d messages from channel %s", messages.size, channel.name);
          }

          // Convert messages to our format
          const validMessages = messages.filter((msg) => !msg.author.bot).map((msg) => fromDiscordMessage(msg));

          channelMessages.push(...validMessages);

          // Update progress
          totalSaved += validMessages.length;
          lastMessageId = messages.last()?.id;
        }

        if (channelMessages.length > 0) {
          await progressMessage.edit({
            content: (
              translations.responses?.progress?.[interaction.locale] ??
              "Saved {saved} messages from {channels} channels..."
            )
              .replace("{saved}", totalSaved.toString())
              .replace("{channels}", totalChannels.toString()),
          });
          await saveChannelMessages(guildId, channelMessages);
          totalChannels++;
        }
      } catch (error) {
        logger.warn("Error saving channel %s: %o", channel.name, error);
      }
    }

    const channelsIds = textChannels.map((channel) => channel.id);
    logger.info("Checked %d channels in guild %s", channelsIds.length, guildId);

    cleanOldChannels(guildId, channelsIds);
    logger.info("Cleaned old channels in guild %s", guildId);

    initializeMessageDays(guildId);
    await optimizeDatabase(guildId);

    await progressMessage.edit({
      content: (
        translations.responses?.success?.[interaction.locale] ??
        "Successfully saved {messages} messages from {channels} channels."
      )
        .replace("{messages}", totalSaved.toString())
        .replace("{channels}", totalChannels.toString()),
    });
  },
};

export default SaveCommand;
