/**
 * A minimal ZIP writer: files stored as they are, without compression.
 *
 * Enough for a folder of PDFs, which are already compressed inside, so
 * deflating them again would save next to nothing — and it keeps a whole
 * compression library out of the bundle for the browsers that need the
 * download fallback.
 */

export type ZipEntry = { name: string; data: Uint8Array };

const CRC_TABLE = (() => {
	const table = new Uint32Array(256);
	for (let n = 0; n < 256; n++) {
		let c = n;
		for (let k = 0; k < 8; k++) {
			c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
		}
		table[n] = c >>> 0;
	}
	return table;
})();

export function crc32(data: Uint8Array): number {
	let crc = 0xffffffff;
	for (const byte of data) {
		crc = CRC_TABLE[(crc ^ byte) & 0xff] ^ (crc >>> 8);
	}
	return (crc ^ 0xffffffff) >>> 0;
}

/** The MS-DOS time and date fields ZIP stores modification times in. */
function dosDateTime(date: Date): { time: number; date: number } {
	return {
		time:
			(date.getHours() << 11) |
			(date.getMinutes() << 5) |
			Math.floor(date.getSeconds() / 2),
		date:
			((Math.max(date.getFullYear(), 1980) - 1980) << 9) |
			((date.getMonth() + 1) << 5) |
			date.getDate(),
	};
}

// bit 11: names are UTF-8, so accented titles survive
const UTF8_NAMES = 0x0800;

export function zip(entries: ZipEntry[], modified = new Date()): Blob {
	const encoder = new TextEncoder();
	const { time, date } = dosDateTime(modified);

	const parts: Uint8Array[] = [];
	const central: Uint8Array[] = [];
	let offset = 0;

	for (const entry of entries) {
		const name = encoder.encode(entry.name);
		const crc = crc32(entry.data);
		const size = entry.data.length;

		const local = new DataView(new ArrayBuffer(30));
		local.setUint32(0, 0x04034b50, true);
		local.setUint16(4, 20, true); // version needed
		local.setUint16(6, UTF8_NAMES, true);
		local.setUint16(8, 0, true); // stored
		local.setUint16(10, time, true);
		local.setUint16(12, date, true);
		local.setUint32(14, crc, true);
		local.setUint32(18, size, true);
		local.setUint32(22, size, true);
		local.setUint16(26, name.length, true);
		local.setUint16(28, 0, true);

		const header = new DataView(new ArrayBuffer(46));
		header.setUint32(0, 0x02014b50, true);
		header.setUint16(4, 20, true); // version made by
		header.setUint16(6, 20, true); // version needed
		header.setUint16(8, UTF8_NAMES, true);
		header.setUint16(10, 0, true);
		header.setUint16(12, time, true);
		header.setUint16(14, date, true);
		header.setUint32(16, crc, true);
		header.setUint32(20, size, true);
		header.setUint32(24, size, true);
		header.setUint16(28, name.length, true);
		// extra length, comment length, disk, internal and external attributes
		// are all zero, which a fresh ArrayBuffer already is
		header.setUint32(42, offset, true);

		parts.push(new Uint8Array(local.buffer), name, entry.data);
		central.push(new Uint8Array(header.buffer), name);
		offset += 30 + name.length + size;
	}

	const centralSize = central.reduce((total, part) => total + part.length, 0);
	const end = new DataView(new ArrayBuffer(22));
	end.setUint32(0, 0x06054b50, true);
	end.setUint16(8, entries.length, true);
	end.setUint16(10, entries.length, true);
	end.setUint32(12, centralSize, true);
	end.setUint32(16, offset, true);

	return new Blob(
		[...parts, ...central, new Uint8Array(end.buffer)] as BlobPart[],
		{
			type: "application/zip",
		},
	);
}
