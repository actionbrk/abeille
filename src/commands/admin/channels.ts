import {
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle,
  ComponentType,
  EmbedBuilder,
  InteractionContextType,
  PermissionFlagsBits,
  SlashCommandBuilder,
} from "discord.js";
import type { Command } from "../../models/command";
import { LocaleHelper } from "../../utils/locale-helper";
import { getChannelStats } from "../../database/bee-database";
import { getAllTextChannels } from "../../utils/channel-helper";

const translations = LocaleHelper.getCommandTranslations("channels");

const MAX_FIELDS_PER_PAGE = 25;
const MAX_FIELD_VALUE_LENGTH = 1024;

const ChannelsCommand: Command = {
  data: new SlashCommandBuilder()
    .setName("channels")
    .setNameLocalizations(translations.localizedNames)
    .setDescription("List all tracked channels and their message counts.")
    .setDescriptionLocalizations(translations.localizedDescriptions)
    .setContexts([InteractionContextType.Guild])
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),
  async execute(interaction) {
    await interaction.deferReply();

    const guildId = interaction.guildId!;
    const guild = interaction.guild!;

    const channelStats = getChannelStats(guildId);
    const viewableChannels = guild.channels.cache.filter((channel) => channel.viewable);

    const textChannels = await getAllTextChannels(viewableChannels);

    const categorizedChannels = new Map<
      string | null,
      { channelName: string; count?: number; threads?: { name: string; count: number }[] }[]
    >();

    textChannels.forEach((channel) => {
      if (!channel.isTextBased()) {
        return;
      }

      if (channel.isThread()) {
        const parentChannel = channel.parent;
        if (!parentChannel) {
          return;
        }

        let threadStats = channelStats.get(channel.id);
        if (!threadStats) {
          threadStats = {
            count: 0,
            firstMessage: new Date(0),
            lastMessage: new Date(0),
          };
        }

        const categoryName = parentChannel.parent?.name ?? null;
        const existingCategory = categorizedChannels.get(categoryName);
        if (!existingCategory) {
          categorizedChannels.set(categoryName, [
            {
              channelName: parentChannel.name,
              count: 0,
              threads: [
                {
                  name: channel.name,
                  count: threadStats.count,
                },
              ],
            },
          ]);
        } else {
          const existingParentChannel = existingCategory.find((ch) => ch.channelName === parentChannel.name);
          if (existingParentChannel) {
            if (!existingParentChannel.threads) {
              existingParentChannel.threads = [];
            }
            existingParentChannel.threads.push({
              name: channel.name,
              count: threadStats.count,
            });
          } else {
            existingCategory.push({
              channelName: parentChannel.name,
              count: 0,
              threads: [
                {
                  name: channel.name,
                  count: threadStats.count,
                },
              ],
            });
          }
        }
      } else {
        const categoryName = channel.parent?.name ?? null;
        const stats = channelStats.get(channel.id);

        if (!categorizedChannels.has(categoryName)) {
          categorizedChannels.set(categoryName, []);
        }

        const existingChannel = categorizedChannels.get(categoryName)!.find((ch) => ch.channelName === channel.name);
        if (existingChannel) {
          existingChannel.count = stats?.count ?? 0;
        } else {
          categorizedChannels.get(categoryName)!.push({
            channelName: channel.name,
            count: stats?.count ?? 0,
            threads: [],
          });
        }
      }
    });

    const sortedCategories = Array.from(categorizedChannels.entries()).sort(([a], [b]) => {
      if (a === null) return 1;
      if (b === null) return -1;
      return a.localeCompare(b);
    });

    const pages: EmbedBuilder[] = [];
    let currentEmbed = new EmbedBuilder()
      .setTitle(translations.responses?.title?.[interaction.locale] ?? "Channel Statistics")
      .setColor(0xffff00);

    let currentFieldCount = 0;

    for (const [category, channels] of sortedCategories) {
      const sortedChannels = channels.sort((a, b) => (b.count ?? 0) - (a.count ?? 0));
      let fieldContent = sortedChannels
        .map((ch) => {
          let result = `#${ch.channelName}:`;
          if (ch.count !== undefined) {
            result += ` ${ch.count.toLocaleString()}`;
          }

          if (ch.threads && ch.threads.length > 0) {
            const sortedThreads = ch.threads.sort((a, b) => b.count - a.count);
            const threadContent = sortedThreads
              .map((thread) => `\n   ├ ${thread.name}: ${thread.count.toLocaleString()}`)
              .join("")
              .replace(/├ ([^\n]*)$/, "└ $1");
            result += threadContent;
          }

          return result;
        })
        .join("\n");

      if (fieldContent.length > MAX_FIELD_VALUE_LENGTH) {
        fieldContent = fieldContent.substring(0, MAX_FIELD_VALUE_LENGTH - 3) + "...";
      }

      if (currentFieldCount >= MAX_FIELDS_PER_PAGE) {
        pages.push(currentEmbed);
        currentEmbed = new EmbedBuilder()
          .setTitle(translations.responses?.title?.[interaction.locale] ?? "Channel Statistics")
          .setColor(0xffff00)
          .setFooter({ text: "" });
        currentFieldCount = 0;
      }

      if (fieldContent.length > 0) {
        currentEmbed.addFields({
          name: category ?? "No Category",
          value: fieldContent,
        });
        currentFieldCount++;
      }
    }

    if (currentFieldCount > 0) {
      pages.push(currentEmbed);
    }

    const totalMessages = Array.from(channelStats.values()).reduce((sum, stats) => sum + stats.count, 0);
    const trackedChannels = channelStats.size;

    pages.forEach((embed, index) => {
      embed.setFooter({
        text: `${(
          translations.responses?.footer?.[interaction.locale] ?? "Total: {total} messages in {channels} channels"
        )
          .replace("{total}", totalMessages.toLocaleString())
          .replace("{channels}", trackedChannels.toString())} (Page ${index + 1}/${pages.length})`,
      });
    });

    if (pages.length === 1) {
      await interaction.editReply({ embeds: [pages[0]!] });
      return;
    }

    let currentPage = 0;
    const row = new ActionRowBuilder<ButtonBuilder>().addComponents(
      new ButtonBuilder().setCustomId("prev").setLabel("◀").setStyle(ButtonStyle.Primary).setDisabled(true),
      new ButtonBuilder()
        .setCustomId("next")
        .setLabel("▶")
        .setStyle(ButtonStyle.Primary)
        .setDisabled(pages.length <= 1)
    );

    const response = await interaction.editReply({
      embeds: [pages[0]!],
      components: [row],
    });

    const collector = response.createMessageComponentCollector({
      componentType: ComponentType.Button,
      time: 300000,
    });

    collector.on("collect", async (i) => {
      if (i.user.id !== interaction.user.id) {
        await i.reply({
          content: translations.responses?.buttonError?.[interaction.locale] ?? "You cannot use these buttons.",
          ephemeral: true,
        });
        return;
      }

      await i.deferUpdate();

      if (i.customId === "prev") {
        if (currentPage > 0) currentPage--;
      } else if (i.customId === "next") {
        if (currentPage < pages.length - 1) currentPage++;
      }

      row.components[0]!.setDisabled(currentPage === 0).setLabel("◀");

      row.components[1]!.setDisabled(currentPage === pages.length - 1).setLabel("▶");

      await i.editReply({
        embeds: [pages[currentPage]!],
        components: [row],
      });
    });

    collector.on("end", async () => {
      row.components.forEach((button) => button.setDisabled(true));
      await response.edit({ components: [row] });
    });
  },
};

export default ChannelsCommand;
