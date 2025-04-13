import {
  ButtonBuilder,
  ButtonStyle,
  ComponentType,
  EmbedBuilder,
  InteractionContextType,
  MessageFlags,
  SlashCommandBuilder,
  TextChannel,
  type ChatInputCommandInteraction,
} from "discord.js";
import type { Command } from "../../models/command";
import { LocaleHelper } from "../../utils/locale-helper";
import { getRandomMessage } from "../../database/bee-database";
import logger from "../../logger";

const translations = LocaleHelper.getCommandTranslations("random");

const RandomCommand: Command = {
  data: new SlashCommandBuilder()
    .setName("random")
    .setNameLocalizations(translations.localizedNames)
    .setDescription("Get a random message from the channel.")
    .setDescriptionLocalizations(translations.localizedDescriptions)
    .setContexts([InteractionContextType.Guild])
    .addChannelOption((option) =>
      option
        .setName("channel")
        .setNameLocalizations(translations.options!.channel!.localizedNames)
        .setDescription("Channel to get message from.")
        .setDescriptionLocalizations(translations.options!.channel!.localizedDescriptions)
    )
    .addBooleanOption((option) =>
      option
        .setName("media")
        .setNameLocalizations(translations.options!.media!.localizedNames)
        .setDescription("Only messages with media.")
        .setDescriptionLocalizations(translations.options!.media!.localizedDescriptions)
    )
    .addIntegerOption((option) =>
      option
        .setName("length")
        .setNameLocalizations(translations.options!.length!.localizedNames)
        .setDescription("Minimum message length.")
        .setDescriptionLocalizations(translations.options!.length!.localizedDescriptions)
        .addChoices({ name: "250+ characters", value: 250 }, { name: "500+ characters", value: 500 })
    )
    .addUserOption((option) =>
      option
        .setName("member")
        .setNameLocalizations(translations.options!.member!.localizedNames)
        .setDescription("Filter by message author.")
        .setDescriptionLocalizations(translations.options!.member!.localizedDescriptions)
    ),
  async execute(interaction) {
    // Check if the command is used in a guild context
    if (!interaction.guild) {
      await interaction.reply({
        content:
          translations.responses?.guildOnly?.[interaction.locale] ?? "This command can only be used in a server.",
        flags: [MessageFlags.Ephemeral],
      });
      return;
    }

    await interaction.deferReply();

    const channel = (interaction.options.getChannel("channel") ?? interaction.channel) as TextChannel;

    // Check NSFW restrictions
    if (
      channel instanceof TextChannel &&
      channel.nsfw &&
      !(interaction.channel instanceof TextChannel && interaction.channel.nsfw)
    ) {
      await interaction.editReply({
        content:
          translations.responses?.nsfwError?.[interaction.locale] ??
          "Cannot fetch messages from NSFW channels in a SFW channel.",
      });
      return;
    }

    await showRandomMessage(interaction, channel);
  },
};

async function showRandomMessage(interaction: ChatInputCommandInteraction, channel: TextChannel) {
  const guildId = interaction.guildId!;
  const media = interaction.options.getBoolean("media") ?? false;
  const length = interaction.options.getInteger("length");
  const member = interaction.options.getUser("member");

  const randomMessage = getRandomMessage(guildId, {
    channelId: channel.id,
    media,
    minLength: length ?? 0,
    authorId: member?.id,
  });

  if (!randomMessage) {
    await interaction.editReply({
      content:
        translations.responses?.noMessageFound?.[interaction.locale] ?? "No message found matching your criteria.",
    });
    return;
  }

  try {
    const discordMessage = await channel.messages.fetch(randomMessage.message_id.toString());

    const embed = new EmbedBuilder()
      .setAuthor({
        name: discordMessage.author.tag,
        iconURL: discordMessage.author.displayAvatarURL(),
      })
      .setDescription(discordMessage.content)
      .setTimestamp(discordMessage.createdAt)
      .setFooter({ text: `#${channel.name}` })
      .setColor(0xffff00);

    // Handle reply context
    if (discordMessage.reference) {
      try {
        const referencedMessage = await channel.messages.fetch(discordMessage.reference.messageId!);
        embed.addFields({
          name: translations.responses?.replyContext?.[interaction.locale] ?? "Replying to",
          value: `**${referencedMessage.author.tag}** · <t:${Math.floor(
            referencedMessage.createdAt.getTime() / 1000
          )}>\n${referencedMessage.content || "[Media content]"}`,
        });
      } catch (error) {
        logger.warn("Could not fetch referenced message: %o", error);
      }
    }

    // Handle attachments
    if (discordMessage.attachments.size > 0) {
      const attachment = discordMessage.attachments.first()!;
      if (attachment.contentType?.startsWith("image/")) {
        embed.setImage(attachment.url);
      } else {
        embed.addFields({
          name: translations.responses?.attachments?.[interaction.locale] ?? "Attachments",
          value: discordMessage.attachments.map((a) => `[${a.name}](${a.url})`).join("\n"),
        });
      }
    }

    const goToMessageButton = new ButtonBuilder()
      .setLabel(translations.responses?.goToMessage?.[interaction.locale] ?? "Go to message")
      .setStyle(ButtonStyle.Link)
      .setURL(discordMessage.url);

    const againButton = new ButtonBuilder()
      .setCustomId("random-again")
      .setLabel(translations.responses?.again?.[interaction.locale] ?? "Another one")
      .setStyle(ButtonStyle.Primary)
      .setEmoji("🔄");

    const row = {
      type: ComponentType.ActionRow,
      components: [goToMessageButton, againButton],
    };

    const message = await interaction.editReply({
      embeds: [embed],
      components: [row],
    });

    const collector = message.createMessageComponentCollector({
      componentType: ComponentType.Button,
      time: 10 * 60 * 1000,
    });

    collector.on("collect", async (i) => {
      if (i.user.id !== interaction.user.id) {
        await i.reply({
          content:
            translations.responses?.notYourButton?.[interaction.locale] ??
            "Only the user who initiated the command can use these buttons.",
          flags: [MessageFlags.Ephemeral],
        });
        return;
      }

      await i.deferUpdate();
      collector.stop();
      await showRandomMessage(interaction, channel);
    });

    collector.on("end", async () => {
      await interaction.editReply({ components: [] });
    });
  } catch (error) {
    logger.error("Error fetching random message: %o", error);
    await interaction.editReply({
      content:
        translations.responses?.error?.[interaction.locale] ?? "An error occurred while fetching the random message.",
    });
  }
}

export default RandomCommand;
