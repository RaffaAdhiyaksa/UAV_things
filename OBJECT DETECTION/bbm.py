class ManajerSPBU:
    def __init__(self):
        self.inventaris = {} 
        self.log_transaksi = []

    def tambah_jenis_bbm(self, nama, harga, stok_awal=0):
        self.inventaris[nama] = {'harga': harga, 'stok': stok_awal}
        print(f"\n[+] Sukses! {nama} terdaftar. Harga: Rp{harga}, Stok: {stok_awal}L")

    def isi_ulang_stok(self, nama, jumlah):
        if nama in self.inventaris:
            self.inventaris[nama]['stok'] += jumlah
            print(f"\n[+] Stok '{nama}' nambah {jumlah}L. Total: {self.inventaris[nama]['stok']}L")
        else:
            print(f"\n[!] Error: BBM '{nama}' gak ada di sistem.")

    def jual_bbm(self, nama, liter):
        if nama not in self.inventaris:
            print(f"\n[!] Error: BBM '{nama}' gak ketemu.")
            return

        data_bbm = self.inventaris[nama]
        if data_bbm['stok'] >= liter:
            total_bayar = liter * data_bbm['harga']
            data_bbm['stok'] -= liter
            
            self.log_transaksi.append({
                'jenis': nama,
                'liter': liter,
                'total': total_bayar
            })
            print(f"\n[✓] Transaksi Berhasil! Total Bayar: Rp{total_bayar}")
        else:
            print(f"\n[!] Gagal: Stok kurang. Sisa cuma {data_bbm['stok']}L")

    def riwayat_transaksi(self):
        print("\n--- RIWAYAT TRANSAKSI ---")
        if not self.log_transaksi:
            print("Belum ada data.")
        else:
            for i, trx in enumerate(self.log_transaksi, 1):
                print(f"{i}. {trx['jenis']} | {trx['liter']}L | Rp{trx['total']}")

    def ringkasan_penjualan(self):
        print("\n--- RINGKASAN PENDAPATAN ---")
        total_omset = sum(item['total'] for item in self.log_transaksi)
        print(f"Total Omset: Rp{total_omset}")

    def update_harga(self, nama, harga_baru):
        if nama in self.inventaris:
            harga_lama = self.inventaris[nama]['harga']
            self.inventaris[nama]['harga'] = harga_baru
            print(f"\n[UPDATE] Harga {nama} berubah: Rp{harga_lama} -> Rp{harga_baru}")
        else:
            print(f"\n[!] Error: BBM '{nama}' tidak ditemukan.")

    def hapus_bbm(self, nama):
        if nama in self.inventaris:
            del self.inventaris[nama]
            print(f"\n[HAPUS] BBM jenis '{nama}' udah dihapus.")
        else:
            print(f"\n[!] Error: BBM '{nama}' gaada")

    def cek_stok_kritis(self, batas_aman=50):
        print(f"\n--- WARNING STOK (Di bawah {batas_aman}L) ---")
        ada_warning = False
        for nama, data in self.inventaris.items():
            if data['stok'] < batas_aman:
                print(f"[!] {nama}: Sisa {data['stok']}L (otw restock!)")
                ada_warning = True
        
        if not ada_warning:
            print("AMAN")

def main():
    spbu = ManajerSPBU()
    
    while True:
        print("\n" + "="*30)
        print("   SISTEM MANAJER SPBU V2.0")
        print("="*30)
        print("1. Tambah Jenis BBM Baru")
        print("2. Isi Ulang Stok (Restock)")
        print("3. Jual BBM")
        print("4. Lihat Riwayat & Omset")
        print("5. Update Harga BBM")
        print("6. Hapus Jenis BBM")
        print("7. Cek Stok Kritis")
        print("0. Keluar")
        
        pilihan = input("Pilih menu (0-7): ")

        if pilihan == '1':
            nama = input("Nama BBM: ")
            harga = int(input("Harga per liter: "))
            stok = float(input("Stok awal: "))
            spbu.tambah_jenis_bbm(nama, harga, stok)

        elif pilihan == '2':
            nama = input("Nama BBM: ")
            jumlah = float(input("Jumlah liter: "))
            spbu.isi_ulang_stok(nama, jumlah)

        elif pilihan == '3':
            nama = input("Beli BBM apa: ")
            liter = float(input("Berapa liter: "))
            spbu.jual_bbm(nama, liter)

        elif pilihan == '4':
            spbu.riwayat_transaksi()
            spbu.ringkasan_penjualan()

        elif pilihan == '5':
            nama = input("Nama BBM yang harganya berubah: ")
            harga_baru = int(input("Harga baru: "))
            spbu.update_harga(nama, harga_baru)

        elif pilihan == '6':
            nama = input("Nama BBM yang mau dihapus: ")
            konfirmasi = input(f"Yakin mau hapus {nama}? (y/n): ")
            if konfirmasi.lower() == 'y':
                spbu.hapus_bbm(nama)
            else:
                print("cancelled")

        elif pilihan == '7':
            batas = input("Masukkan batas minimal (Enter untuk default 50): ")
            if batas == "":
                spbu.cek_stok_kritis()
            else:
                spbu.cek_stok_kritis(float(batas))

        elif pilihan == '0':
            print("Sistem dimatikan.")
            break

        else:
            print("\nPilihan salah bos.")

if __name__ == "__main__":
    main()