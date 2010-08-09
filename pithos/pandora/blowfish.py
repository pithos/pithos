#
# blowfish.py
# Copyright (C) 2002 Michael Gilfix <mgilfix@eecs.tufts.edu>
#
# This module is open source; you can redistribute it and/or
# modify it under the terms of the GPL or Artistic License.
# These licenses are available at http://www.opensource.org
#
# This software must be used and distributed in accordance
# with the law. The author claims no liability for its
# misuse.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#

"""
Blowfish Encryption

This module is a pure python implementation of Bruce Schneier's
encryption scheme 'Blowfish'. Blowish is a 16-round Feistel Network
cipher and offers substantial speed gains over DES.

The key is a string of length anywhere between 64 and 448 bits, or
equivalently 8 and 56 bytes. The encryption and decryption functions operate
on 64-bit blocks, or 8 byte strings.

Send questions, comments, bugs my way:
    Michael Gilfix <mgilfix@eecs.tufts.edu>
    
This version is modified by Kevin Mehall <km@kevinmehall.net> to accept the 
S and P boxes directly, rather than computing them from a key
"""

__author__ = "Michael Gilfix <mgilfix@eecs.tufts.edu>"

class Blowfish:

	"""Blowfish encryption Scheme

	This class implements the encryption and decryption
	functionality of the Blowfish cipher.

	Public functions:

		def __init__ (self, key)
			Creates an instance of blowfish using 'key'
			as the encryption key. Key is a string of
			length ranging from 8 to 56 bytes (64 to 448
			bits). Once the instance of the object is
			created, the key is no longer necessary.

		def encrypt (self, data):
			Encrypt an 8 byte (64-bit) block of text
			where 'data' is an 8 byte string. Returns an
			8-byte encrypted string.

		def decrypt (self, data):
			Decrypt an 8 byte (64-bit) encrypted block
			of text, where 'data' is the 8 byte encrypted
			string. Returns an 8-byte string of plaintext.

		def cipher (self, xl, xr, direction):
			Encrypts a 64-bit block of data where xl is
			the upper 32-bits and xr is the lower 32-bits.
			'direction' is the direction to apply the
			cipher, either ENCRYPT or DECRYPT constants.
			returns a tuple of either encrypted or decrypted
			data of the left half and right half of the
			64-bit block.

	Private members:

		def __round_func (self, xl)
			Performs an obscuring function on the 32-bit
			block of data 'xl', which is the left half of
			the 64-bit block of data. Returns the 32-bit
			result as a long integer.

	"""

	# Cipher directions
	ENCRYPT = 0
	DECRYPT = 1

	# For the __round_func
	modulus = long (2) ** 32

	def __init__ (self, p_boxes, s_boxes):
		self.p_boxes = p_boxes
		self.s_boxes = s_boxes
		

	def cipher (self, xl, xr, direction):

		if direction == self.ENCRYPT:
			for i in range (16):
				xl = xl ^ self.p_boxes[i]
				xr = self.__round_func (xl) ^ xr
				xl, xr = xr, xl
			xl, xr = xr, xl
			xr = xr ^ self.p_boxes[16]
			xl = xl ^ self.p_boxes[17]
		else:
			for i in range (17, 1, -1):
				xl = xl ^ self.p_boxes[i]
				xr = self.__round_func (xl) ^ xr
				xl, xr = xr, xl
			xl, xr = xr, xl
			xr = xr ^ self.p_boxes[1]
			xl = xl ^ self.p_boxes[0]
		return xl, xr

	def __round_func (self, xl):
		a = (xl & 0xFF000000) >> 24
		b = (xl & 0x00FF0000) >> 16
		c = (xl & 0x0000FF00) >> 8
		d = xl & 0x000000FF

		# Perform all ops as longs then and out the last 32-bits to
		# obtain the integer
		f = (long (self.s_boxes[0][a]) + long (self.s_boxes[1][b])) % self.modulus
		f = f ^ long (self.s_boxes[2][c])
		f = f + long (self.s_boxes[3][d])
		f = (f % self.modulus) & 0xFFFFFFFF

		return f

	def encrypt (self, data):

		if not len (data) == 8:
			raise RuntimeError, "Attempted to encrypt data of invalid block length: %s" %len (data)

		# Use big endianess since that's what everyone else uses
		xl = ord (data[3]) | (ord (data[2]) << 8) | (ord (data[1]) << 16) | (ord (data[0]) << 24)
		xr = ord (data[7]) | (ord (data[6]) << 8) | (ord (data[5]) << 16) | (ord (data[4]) << 24)

		cl, cr = self.cipher (xl, xr, self.ENCRYPT)
		chars = ''.join ([
			chr ((cl >> 24) & 0xFF), chr ((cl >> 16) & 0xFF), chr ((cl >> 8) & 0xFF), chr (cl & 0xFF),
			chr ((cr >> 24) & 0xFF), chr ((cr >> 16) & 0xFF), chr ((cr >> 8) & 0xFF), chr (cr & 0xFF)
		])
		return chars

	def decrypt (self, data):

		if not len (data) == 8:
			raise RuntimeError, "Attempted to encrypt data of invalid block length: %s" %len (data)

		# Use big endianess since that's what everyone else uses
		cl = ord (data[3]) | (ord (data[2]) << 8) | (ord (data[1]) << 16) | (ord (data[0]) << 24)
		cr = ord (data[7]) | (ord (data[6]) << 8) | (ord (data[5]) << 16) | (ord (data[4]) << 24)

		xl, xr = self.cipher (cl, cr, self.DECRYPT)
		chars = ''.join ([
			chr ((xl >> 24) & 0xFF), chr ((xl >> 16) & 0xFF), chr ((xl >> 8) & 0xFF), chr (xl & 0xFF),
			chr ((xr >> 24) & 0xFF), chr ((xr >> 16) & 0xFF), chr ((xr >> 8) & 0xFF), chr (xr & 0xFF)
		])
		return chars

	def blocksize (self):
		return 8

	def key_length (self):
		return 56

	def key_bits (self):
		return 56 * 8

	
