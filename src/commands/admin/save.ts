import {
  ChatInputCommandInteraction,
  Guild,
  InteractionContextType,
  Message,
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
import { fromDiscordMessage, messageHasContentOrUrl } from "../../models/database/message";
import logger from "../../logger";
import { getSnowflakeFromDate } from "../../utils/snowflake-helper";

const translations = LocaleHelper.getCommandTranslations("save");

const SaveCommand: Command = {
  data: new SlashCommandBuilder()
    .setName("save")
    .setNameLocalizations(translations.localizedNames)
    .setDescription("Force a complete save of all messages.")
    .setDescriptionLocalizations(translations.localizedDescriptions)
    .setContexts([InteractionContextType.Guild])
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator)
    .addIntegerOption((option) => option.setName("since")
      .setNameLocalizations(translations.options!.since!.localizedNames)
      .setDescription("Save messages since a specific date.")
      .setDescriptionLocalizations(translations.options!.since!.localizedDescriptions)
      .addChoices(
        {
          name: "1 day",
          name_localizations: translations.options?.since?.choices?.oneDay?.localizedNames,
          value: 1,
        },
        {
          name: "1 week",
          name_localizations: translations.options?.since?.choices?.oneWeek?.localizedNames,
          value: 7,
        }
      )
    ),
  async execute(interaction) {
    await interaction.deferReply();

    const guild = interaction.guild!;
    const since = interaction.options.getInteger("since");

    let lastMessageId: string | undefined;
    if (since) {
      const sinceDate = new Date();
      sinceDate.setDate(sinceDate.getDate() - since);
      lastMessageId = getSnowflakeFromDate(sinceDate)
    }

    await saveMessagesForGuild(guild, lastMessageId, interaction);
  },
};

export default SaveCommand;

/**
 * Saves messages from a guild to the database.
 * @param {Guild} guild - The guild to save messages from.
 * @param {string | null} since - The snowflake of the messages to start saving from.
 * @param {ChatInputCommandInteraction} [interaction] - The interaction that triggered the command.
 * @returns {Promise<void>} - A promise that resolves when the operation is complete.
 */
export async function saveMessagesForGuild(guild: Guild, since: string | undefined, interaction?: ChatInputCommandInteraction): Promise<void> {
  logger.info("Saving messages for guild %s", guild.id);

  const guildId = guild.id;

  let totalSaved = 0;
  let totalChannels = 0;

  // Get all text channels
  const textChannels = guild.channels.cache.filter((channel) => channel.viewable);

  let progressMessage: Message<boolean> | null = null;
  if (interaction) {
    progressMessage = await interaction.editReply({
      content: translations.responses?.scanning?.[interaction.locale] ?? "Scanning channels for messages...",
    });
  }

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

        if (since) {
          if (!lastMessageId) {
            options.after = since;
          } else {
            options.after = lastMessageId;
          }
        } else if (lastMessageId) {
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
        const validMessages = messages
          .filter((msg) => !msg.author.bot)
          .map((msg) => fromDiscordMessage(msg))
          .filter((msg) => messageHasContentOrUrl(msg));

        channelMessages.push(...validMessages);

        // Update progress
        totalSaved += validMessages.length;

        if (since) {
          lastMessageId = messages.first()?.id;
        } else {
          lastMessageId = messages.last()?.id;
        }
      }

      if (channelMessages.length > 0) {
        if (progressMessage && interaction) {
          await progressMessage.edit({
            content: (
              translations.responses?.progress?.[interaction.locale] ??
              "Saved {saved} messages from {channels} channels..."
            )
              .replace("{saved}", totalSaved.toString())
              .replace("{channels}", totalChannels.toString()),
          });
        }
        await saveChannelMessages(guildId, channelMessages);
        totalChannels++;

        logger.info("Saved %d messages from channel %s", channelMessages.length, channel.name);
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

  if (progressMessage && interaction) {
    await progressMessage.edit({
      content: (
        translations.responses?.success?.[interaction.locale] ??
        "Successfully saved {messages} messages from {channels} channels."
      )
        .replace("{messages}", totalSaved.toString())
        .replace("{channels}", totalChannels.toString()),
    });
  }
}

