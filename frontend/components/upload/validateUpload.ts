/**
 * Client-side checks before anything is sent. The backend repeats them (and also
 * counts PDF pages); these mirror its rules in backend/app/services/extraction.py.
 */

export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const EXTENSIONS = new Set(["pdf", "png", "jpg", "jpeg"]);
const PNG_SIGNATURE = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];

export const UPLOAD_ACCEPT = ".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg";

async function looksLikeSupportedFile(file: File): Promise<boolean> {
  const head = new Uint8Array(await file.slice(0, 1024).arrayBuffer());
  if (PNG_SIGNATURE.every((byte, i) => head[i] === byte)) return true;
  if (head[0] === 0xff && head[1] === 0xd8 && head[2] === 0xff) return true;
  // The PDF spec allows the "%PDF-" header anywhere in the first 1024 bytes.
  return new TextDecoder("latin1").decode(head).includes("%PDF-");
}

export function fileExtension(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot + 1).toLowerCase() : "";
}

/** A user-facing error message, or null if the file can be uploaded. */
export async function validateUpload(file: File): Promise<string | null> {
  if (!EXTENSIONS.has(fileExtension(file.name))) return "Unsupported format. Please choose a PDF, PNG, or JPG file.";
  if (file.size === 0) return "This file is empty.";
  if (file.size > MAX_UPLOAD_BYTES) {
    return `This file is ${(file.size / 1048576).toFixed(1)} MB. The limit is 10 MB per file.`;
  }
  if (!(await looksLikeSupportedFile(file))) {
    return "This file's contents don't look like a PDF, PNG, or JPG. It may be corrupted or renamed.";
  }
  return null;
}
