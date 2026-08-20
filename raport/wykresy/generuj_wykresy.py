import os
import re
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Ustawienia stylu matplotlib dla estetycznych wykresów inżynierskich
plt.rcParams['font.sans-serif'] = 'Segoe UI', 'DejaVu Sans', 'Arial'
plt.rcParams['axes.edgecolor'] = '#cccccc'
plt.rcParams['axes.linewidth'] = 1.0

def load_cfd_data(excel_path):
    """Wczytuje dane CFD z pliku Excel."""
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Nie znaleziono pliku: {excel_path}")
    
    # Odczyt arkusza do znalezienia wiersza z nagłówkami
    raw_df = pd.read_excel(excel_path, sheet_name=0, header=None)
    
    header_idx = None
    for idx, row in raw_df.iterrows():
        row_str = " ".join([str(val) for val in row.values if pd.notna(val)])
        if 'V[m/s]' in row_str or 'Si' in row_str:
            header_idx = idx
            break
            
    if header_idx is None:
        header_idx = 6 # Domyślny wiersz z nagłówkiem
        
    df = pd.read_excel(excel_path, sheet_name=0, header=header_idx)
    df = df.dropna(how='all', axis=1).dropna(how='all', axis=0)
    df.columns = [str(c).strip() for c in df.columns]
    
    # Mapowanie nazw kolumn
    col_map = {}
    for col in df.columns:
        if 'V' in col:
            col_map[col] = 'V'
        elif 'Si' in col or 'T' in col:
            col_map[col] = 'Sila'
        elif 'Moment' in col or 'Q' in col:
            col_map[col] = 'Moment'
        elif 'Moc' in col or 'P' in col:
            col_map[col] = 'Moc'
        elif 'sprawno' in col.lower() or 'eta' in col.lower():
            col_map[col] = 'Sprawnosc'
        elif 'J' in col:
            col_map[col] = 'J'
            
    df = df.rename(columns=col_map)
    
    # Czyszczenie i konwersja typów danych
    for c in ['V', 'Sila', 'Moment', 'Moc', 'Sprawnosc', 'J']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
            
    df = df.dropna(subset=['V']).sort_values(by='V').reset_index(drop=True)
    
    # UWAGA: Dane w pliku excel podane są dla połowy śmigła (1/2 modelu).
    # Pomnożenie siły i momentu dwukrotnie dla odzwierciedlenia pełnego śmigła.
    df['Sila'] = df['Sila'] * 2.0
    df['Moment'] = df['Moment'] * 2.0
    
    # Przeliczenie mocy dla pełnego śmigła (P = omega * Q_full, omega = 2*pi*3000/60 = 314,159 rad/s)
    # Dla ujemnego momentu zachowujemy odpowiedni znak mocy
    OMEGA = 2.0 * np.pi * 3000.0 / 60.0  # 314,159 rad/s dla n = 3000 RPM
    df['Moc'] = df['Moment'] * OMEGA
    
    # Przeliczenie sprawności eta = (T_full * V) / P_full * 100%
    # Dla V=0 lub P<=0 sprawność wynosi 0%
    sprawnosc_calc = []
    for v, t, p in zip(df['V'], df['Sila'], df['Moc']):
        if v > 0 and p > 0 and t > 0:
            sprawnosc_calc.append((t * v / p) * 100.0)
        else:
            sprawnosc_calc.append(0.0)
    df['Sprawnosc'] = sprawnosc_calc

    return df

def load_bmt_data(bmt_txt_path=None):
    """Wczytuje lub zwraca zdefiniowane dane BMT (BEMT)."""
    if bmt_txt_path and os.path.exists(bmt_txt_path):
        try:
            with open(bmt_txt_path, 'r', encoding='cp1250') as f:
                lines = f.readlines()
            v_list, t_list, q_list, p_list, eta_list, j_list = [], [], [], [], [], []
            for line in lines:
                parts = line.strip().split('|')
                if len(parts) >= 8:
                    try:
                        v_val = float(parts[0].strip())
                        t_val = float(parts[1].strip())
                        q_val = float(parts[2].strip())
                        p_val = float(parts[3].strip())
                        eta_val = float(parts[4].strip()) * 100.0 # konwersja na %
                        j_val = float(parts[7].strip())
                        
                        v_list.append(v_val)
                        t_list.append(t_val)
                        q_list.append(q_val)
                        p_list.append(p_val)
                        eta_list.append(eta_val)
                        j_list.append(j_val)
                    except ValueError:
                        continue
            if len(v_list) > 0:
                return pd.DataFrame({
                    'V': v_list, 'Sila': t_list, 'Moment': q_list,
                    'Moc': p_list, 'Sprawnosc': eta_list, 'J': j_list
                })
        except Exception as e:
            print(f"Uwaga: Nie udało się odczytać podsumowanie_wynikow.txt: {e}")

    # Domyślne wartości z BEMT
    return pd.DataFrame({
        'V': [0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0],
        'Sila': [27.260, 25.364, 21.394, 15.105, 7.487, -1.505, -9.935],
        'Moment': [0.906, 1.037, 1.072, 0.919, 0.568, -0.035, -0.697],
        'Moc': [284.62, 325.73, 336.63, 288.76, 178.46, -11.06, -218.98],
        'Sprawnosc': [0.0, 38.9, 63.6, 78.5, 83.9, 0.0, 0.0],
        'J': [0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2]
    })

def create_charts():
    output_dir = os.path.dirname(os.path.abspath(__file__))
    excel_path = os.path.join(output_dir, "..", "propeller.xlsx")
    bmt_path = os.path.join(output_dir, "..", "..", "BMF", "podsumowanie_wynikow.txt")

    if not os.path.exists(excel_path):
        excel_path = r"F:\DRS\raport\propeller.xlsx"
    if not os.path.exists(bmt_path):
        bmt_path = r"F:\DRS\BMF\podsumowanie_wynikow.txt"

    print(f"Wczytywanie CFD z: {excel_path}")
    df_cfd = load_cfd_data(excel_path)

    print(f"Wczytywanie BMT z: {bmt_path}")
    df_bmt = load_bmt_data(bmt_path)

    # Kolory i stylizacja
    COLOR_CFD = '#0055D4'      # Głęboki błękit dla CFD
    COLOR_BMT = '#E65100'      # Pomarańczowo-czerwony dla BMT
    COLOR_ERROR = '#8E24AA'    # Purpura dla błędów

    # --- 1. WYKRESY SYMULACJI CFD ---

    # 1. CFD: Siła od prędkości
    fig, ax = plt.subplots(figsize=(8, 5.5), dpi=300)
    ax.plot(df_cfd['V'], df_cfd['Sila'], 'o-', color=COLOR_CFD, linewidth=2.2, markersize=7, label='CFD')
    ax.set_title('Symulacja CFD: Zależność siły ciągu od prędkości', fontsize=13, fontweight='bold', pad=12)
    ax.set_xlabel(r'Prędkość $V$ [m/s]', fontsize=11, labelpad=8)
    ax.set_ylabel(r'Siła ciągu $T$ [N]', fontsize=11, labelpad=8)
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.legend(loc='best', frameon=True, facecolor='white', framealpha=0.9)
    plt.tight_layout()
    p1 = os.path.join(output_dir, "01_cfd_sila_od_predkosci.png")
    plt.savefig(p1, dpi=300)
    plt.close()

    # 2. CFD: Moment od prędkości
    fig, ax = plt.subplots(figsize=(8, 5.5), dpi=300)
    ax.plot(df_cfd['V'], df_cfd['Moment'], 's-', color=COLOR_CFD, linewidth=2.2, markersize=7, label='CFD')
    ax.set_title('Symulacja CFD: Zależność momentu obrotowego od prędkości', fontsize=13, fontweight='bold', pad=12)
    ax.set_xlabel(r'Prędkość $V$ [m/s]', fontsize=11, labelpad=8)
    ax.set_ylabel(r'Moment $Q$ [Nm]', fontsize=11, labelpad=8)
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.legend(loc='best', frameon=True, facecolor='white', framealpha=0.9)
    plt.tight_layout()
    p2 = os.path.join(output_dir, "02_cfd_moment_od_predkosci.png")
    plt.savefig(p2, dpi=300)
    plt.close()

    # 3. CFD: Sprawność od prędkości
    fig, ax = plt.subplots(figsize=(8, 5.5), dpi=300)
    ax.plot(df_cfd['V'], df_cfd['Sprawnosc'], '^-', color=COLOR_CFD, linewidth=2.2, markersize=7, label='CFD')
    ax.set_title('Symulacja CFD: Zależność sprawności od prędkości', fontsize=13, fontweight='bold', pad=12)
    ax.set_xlabel(r'Prędkość $V$ [m/s]', fontsize=11, labelpad=8)
    ax.set_ylabel(r'Sprawność $\eta$ [%]', fontsize=11, labelpad=8)
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.legend(loc='best', frameon=True, facecolor='white', framealpha=0.9)
    plt.tight_layout()
    p3 = os.path.join(output_dir, "03_cfd_sprawnosc_od_predkosci.png")
    plt.savefig(p3, dpi=300)
    plt.close()

    # 4. CFD: Sprawność od J
    fig, ax = plt.subplots(figsize=(8, 5.5), dpi=300)
    ax.plot(df_cfd['J'], df_cfd['Sprawnosc'], 'd-', color=COLOR_CFD, linewidth=2.2, markersize=7, label='CFD')
    ax.set_title('Symulacja CFD: Zależność sprawności od współczynnika $J$', fontsize=13, fontweight='bold', pad=12)
    ax.set_xlabel(r'Współczynnik zaawansowania $J$ [-]', fontsize=11, labelpad=8)
    ax.set_ylabel(r'Sprawność $\eta$ [%]', fontsize=11, labelpad=8)
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.legend(loc='best', frameon=True, facecolor='white', framealpha=0.9)
    plt.tight_layout()
    p4 = os.path.join(output_dir, "04_cfd_sprawnosc_od_J.png")
    plt.savefig(p4, dpi=300)
    plt.close()

    # --- 2. WYKRESY PORÓWNAWCZE (CFD VS BMT) ---

    # 5. Porównanie: Sprawność od prędkości
    fig, ax = plt.subplots(figsize=(8, 5.5), dpi=300)
    ax.plot(df_cfd['V'], df_cfd['Sprawnosc'], 'o-', color=COLOR_CFD, linewidth=2.2, markersize=7, label='CFD')
    ax.plot(df_bmt['V'], df_bmt['Sprawnosc'], 's--', color=COLOR_BMT, linewidth=2.2, markersize=7, label='BMT')
    ax.set_title('Porównanie sprawności w zależności od prędkości (CFD vs BMT)', fontsize=13, fontweight='bold', pad=12)
    ax.set_xlabel(r'Prędkość $V$ [m/s]', fontsize=11, labelpad=8)
    ax.set_ylabel(r'Sprawność $\eta$ [%]', fontsize=11, labelpad=8)
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.legend(loc='best', frameon=True, facecolor='white', framealpha=0.9)
    plt.tight_layout()
    p5 = os.path.join(output_dir, "05_porownanie_sprawnosc_od_predkosci.png")
    plt.savefig(p5, dpi=300)
    plt.close()

    # 6. Porównanie: Siła od prędkości
    fig, ax = plt.subplots(figsize=(8, 5.5), dpi=300)
    ax.plot(df_cfd['V'], df_cfd['Sila'], 'o-', color=COLOR_CFD, linewidth=2.2, markersize=7, label='CFD')
    ax.plot(df_bmt['V'], df_bmt['Sila'], 's--', color=COLOR_BMT, linewidth=2.2, markersize=7, label='BMT')
    ax.set_title('Porównanie siły ciągu w zależności od prędkości (CFD vs BMT)', fontsize=13, fontweight='bold', pad=12)
    ax.set_xlabel(r'Prędkość $V$ [m/s]', fontsize=11, labelpad=8)
    ax.set_ylabel(r'Siła ciągu $T$ [N]', fontsize=11, labelpad=8)
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.legend(loc='best', frameon=True, facecolor='white', framealpha=0.9)
    plt.tight_layout()
    p6 = os.path.join(output_dir, "06_porownanie_sila_od_predkosci.png")
    plt.savefig(p6, dpi=300)
    plt.close()

    # 7. Porównanie: Moment od prędkości
    fig, ax = plt.subplots(figsize=(8, 5.5), dpi=300)
    ax.plot(df_cfd['V'], df_cfd['Moment'], 'o-', color=COLOR_CFD, linewidth=2.2, markersize=7, label='CFD')
    ax.plot(df_bmt['V'], df_bmt['Moment'], 's--', color=COLOR_BMT, linewidth=2.2, markersize=7, label='BMT')
    ax.set_title('Porównanie momentu w zależności od prędkości (CFD vs BMT)', fontsize=13, fontweight='bold', pad=12)
    ax.set_xlabel(r'Prędkość $V$ [m/s]', fontsize=11, labelpad=8)
    ax.set_ylabel(r'Moment $Q$ [Nm]', fontsize=11, labelpad=8)
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.legend(loc='best', frameon=True, facecolor='white', framealpha=0.9)
    plt.tight_layout()
    p7 = os.path.join(output_dir, "07_porownanie_moment_od_predkosci.png")
    plt.savefig(p7, dpi=300)
    plt.close()

    # --- 3. WYKRESY BŁĘDU WZGLĘDNEGO (CFD VS BMT) ---

    def calc_rel_error(cfd_vals, bmt_vals):
        errs = []
        for c, b in zip(cfd_vals, bmt_vals):
            if b == 0:
                errs.append(0.0)
            else:
                errs.append(((c - b) / abs(b)) * 100.0)
        return np.array(errs)

    err_moc = calc_rel_error(df_cfd['Moc'], df_bmt['Moc'])
    err_sila = calc_rel_error(df_cfd['Sila'], df_bmt['Sila'])
    err_moment = calc_rel_error(df_cfd['Moment'], df_bmt['Moment'])
    err_sprawnosc = calc_rel_error(df_cfd['Sprawnosc'], df_bmt['Sprawnosc'])

    # Helper do dodawania ulepszonych adnotacji
    def annotate_errors(ax, v_vals, err_vals):
        y_min, y_max = min(err_vals), max(err_vals)
        margin = max(abs(y_min), abs(y_max)) * 0.25 if max(abs(y_min), abs(y_max)) > 0 else 10
        ax.set_ylim(y_min - margin, y_max + margin)
        
        for v, e in zip(v_vals, err_vals):
            offset = (8 if e >= 0 else -14)
            ax.annotate(f'{e:+.1f}%', (v, e), textcoords="offset points", xytext=(0, offset),
                        ha='center', fontsize=8.5, fontweight='bold', color='#4A148C',
                        bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='none', alpha=0.7))

    # 8. Błąd względny: Moc
    fig, ax = plt.subplots(figsize=(8, 5.5), dpi=300)
    ax.plot(df_cfd['V'], err_moc, 'D-', color=COLOR_ERROR, linewidth=2.2, markersize=7, label=r'Błąd względny mocy $\delta P$')
    ax.axhline(0, color='gray', linestyle='--', linewidth=1)
    ax.set_title('Błąd względny mocy w zależności od prędkości (CFD vs BMT)', fontsize=13, fontweight='bold', pad=12)
    ax.set_xlabel(r'Prędkość $V$ [m/s]', fontsize=11, labelpad=8)
    ax.set_ylabel(r'Błąd względny $\delta P$ [%]', fontsize=11, labelpad=8)
    ax.grid(True, linestyle='--', alpha=0.6)
    annotate_errors(ax, df_cfd['V'], err_moc)
    ax.legend(loc='best', frameon=True, facecolor='white', framealpha=0.9)
    plt.tight_layout()
    p8 = os.path.join(output_dir, "08_blad_wzgledny_moc.png")
    plt.savefig(p8, dpi=300)
    plt.close()

    # 9. Błąd względny: Siła ciągu
    fig, ax = plt.subplots(figsize=(8, 5.5), dpi=300)
    ax.plot(df_cfd['V'], err_sila, 'D-', color=COLOR_ERROR, linewidth=2.2, markersize=7, label=r'Błąd względny siły $\delta T$')
    ax.axhline(0, color='gray', linestyle='--', linewidth=1)
    ax.set_title('Błąd względny siły ciągu w zależności od prędkości (CFD vs BMT)', fontsize=13, fontweight='bold', pad=12)
    ax.set_xlabel(r'Prędkość $V$ [m/s]', fontsize=11, labelpad=8)
    ax.set_ylabel(r'Błąd względny $\delta T$ [%]', fontsize=11, labelpad=8)
    ax.grid(True, linestyle='--', alpha=0.6)
    annotate_errors(ax, df_cfd['V'], err_sila)
    ax.legend(loc='best', frameon=True, facecolor='white', framealpha=0.9)
    plt.tight_layout()
    p9 = os.path.join(output_dir, "09_blad_wzgledny_sila.png")
    plt.savefig(p9, dpi=300)
    plt.close()

    # 10. Błąd względny: Sprawność
    fig, ax = plt.subplots(figsize=(8, 5.5), dpi=300)
    ax.plot(df_cfd['V'], err_sprawnosc, 'D-', color=COLOR_ERROR, linewidth=2.2, markersize=7, label=r'Błąd względny sprawności $\delta \eta$')
    ax.axhline(0, color='gray', linestyle='--', linewidth=1)
    ax.set_title('Błąd względny sprawności w zależności od prędkości (CFD vs BMT)', fontsize=13, fontweight='bold', pad=12)
    ax.set_xlabel(r'Prędkość $V$ [m/s]', fontsize=11, labelpad=8)
    ax.set_ylabel(r'Błąd względny $\delta \eta$ [%]', fontsize=11, labelpad=8)
    ax.grid(True, linestyle='--', alpha=0.6)
    annotate_errors(ax, df_cfd['V'], err_sprawnosc)
    ax.legend(loc='best', frameon=True, facecolor='white', framealpha=0.9)
    plt.tight_layout()
    p10 = os.path.join(output_dir, "10_blad_wzgledny_sprawnosc.png")
    plt.savefig(p10, dpi=300)
    plt.close()

    # --- 4. ZAPIS NAJWAŻNIEJSZYCH DANYCH DO PLIKU TEKSTOWEGO ---
    txt_content = []
    txt_content.append("="*85)
    txt_content.append("    ZBIORCZE PODSUMOWANIE WYNIKÓW SYMULACJI CFD, METODY BMT ORAZ BŁĘDÓW WZGLĘDNYCH")
    txt_content.append("="*85 + "\n")
    txt_content.append("Uwaga: Dane CFD zostały przeliczone dla pełnego śmigła (wartości siły i momentu z pliku Excel")
    txt_content.append("pomnożono 2x, ponieważ w oryginale dotyczyły 1/2 modelu śmigła).\n")

    txt_content.append("1. WYNIKI SYMULACJI CFD (PEŁNE ŚMIGŁO):")
    txt_content.append(f"{'V [m/s]':>8} | {'T_CFD [N]':>11} | {'Q_CFD [Nm]':>12} | {'P_CFD [W]':>11} | {'eta_CFD [%]':>12} | {'J [-]':>8}")
    txt_content.append("-" * 75)
    for v, t, q, p, e, j in zip(df_cfd['V'], df_cfd['Sila'], df_cfd['Moment'], df_cfd['Moc'], df_cfd['Sprawnosc'], df_cfd['J']):
        txt_content.append(f"{v:8.1f} | {t:11.4f} | {q:12.4f} | {p:11.2f} | {e:12.2f} | {j:8.4f}")

    txt_content.append("\n2. WYNIKI METODY BMT:")
    txt_content.append(f"{'V [m/s]':>8} | {'T_BMT [N]':>11} | {'Q_BMT [Nm]':>12} | {'P_BMT [W]':>11} | {'eta_BMT [%]':>12} | {'J [-]':>8}")
    txt_content.append("-" * 75)
    for v, t, q, p, e, j in zip(df_bmt['V'], df_bmt['Sila'], df_bmt['Moment'], df_bmt['Moc'], df_bmt['Sprawnosc'], df_bmt['J']):
        txt_content.append(f"{v:8.1f} | {t:11.4f} | {q:12.4f} | {p:11.2f} | {e:12.2f} | {j:8.4f}")

    txt_content.append("\n3. BŁĘDY WZGLĘDNE METODY CFD WZGLĘDEM BMT [(CFD - BMT) / |BMT| * 100%]:")
    txt_content.append(f"{'V [m/s]':>8} | {'err_T [%]':>11} | {'err_Q [%]':>11} | {'err_P [%]':>11} | {'err_eta [%]':>12}")
    txt_content.append("-" * 65)
    for v, et, eq, ep, ee in zip(df_cfd['V'], err_sila, err_moment, err_moc, err_sprawnosc):
        txt_content.append(f"{v:8.1f} | {et:+11.2f}% | {eq:+11.2f}% | {ep:+11.2f}% | {ee:+12.2f}%")

    txt_content.append("\n" + "="*85)

    txt_str = "\n".join(txt_content)

    # Zapis pliku w folderze wykresy oraz w głównym folderze raport
    txt_path_wykresy = os.path.join(output_dir, "podsumowanie_danych.txt")
    txt_path_raport = os.path.join(output_dir, "..", "podsumowanie_danych.txt")

    with open(txt_path_wykresy, "w", encoding="utf-8") as f:
        f.write(txt_str)
    with open(txt_path_raport, "w", encoding="utf-8") as f:
        f.write(txt_str)

    print(f"Zapisano dane tekstowe w: {txt_path_wykresy}")
    print(f"Zapisano dane tekstowe w: {txt_path_raport}")

    print("\n--- Pomyślnie utworzono i wygenerowano wszystkie 10 wykresów oraz plik tekstowy z danymi ---")

if __name__ == "__main__":
    create_charts()
