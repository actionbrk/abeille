import { InteractionContextType, MessageFlags, SlashCommandBuilder } from "discord.js";
import type { Command } from "../../models/command";
import { LocaleHelper } from "../../utils/locale-helper";
import { exportUserMessages } from "../../database/bee-database";
import * as csvStringify from "csv-stringify/sync";
import { BlobWriter, ZipWriter } from "@zip.js/zip.js";

const translations = LocaleHelper.getCommandTranslations("export");

const ExportCommand: Command = {
  data: new SlashCommandBuilder()
    .setName("export")
    .setNameLocalizations(translations.localizedNames)
    .setDescription("Download your personal data collected by Abeille.")
    .setDescriptionLocalizations(translations.localizedDescriptions)
    .setContexts([InteractionContextType.Guild]),
  async execute(interaction) {
    await interaction.deferReply({ flags: [MessageFlags.Ephemeral] });

    const guildId = interaction.guildId!;
    const userId = interaction.user.id;

    const messages = exportUserMessages(guildId, userId);

    if (messages.length === 0) {
      await interaction.editReply({
        content: translations.responses?.noData?.[interaction.locale] ?? "No data found for you in this guild.",
      });
      return;
    }

    // Convert messages to CSV
    const csvString = csvStringify.stringify(messages, {
      header: true,
      columns: ["message_id", "channel_id", "timestamp", "content", "attachment_url"],
    });

    // Create ZIP file
    const zipWriter = new ZipWriter(new BlobWriter("application/zip"));
    await zipWriter.add("messages.csv", new Blob([csvString]).stream());
    const zipBlob = await zipWriter.close();
    const buffer = Buffer.from(await zipBlob.arrayBuffer());

    // Send file via DM
    const dmChannel = await interaction.user.createDM();
    await dmChannel.send({
      content:
        translations.responses?.dmIntro?.[interaction.locale] ??
        "Here are your messages collected by Abeille. You can use /delete <message_id> to remove specific messages.",
      files: [
        {
          attachment: buffer,
          name: "abeille_data.zip",
        },
      ],
    });

    await interaction.editReply({
      content: translations.responses?.success?.[interaction.locale] ?? "Your data has been sent to you via DM.",
    });
  },
};

export default ExportCommand;
