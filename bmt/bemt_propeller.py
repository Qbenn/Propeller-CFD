import numpy as np
from scipy.interpolate import interp1d
import os
import re
import matplotlib.pyplot as plt

# ============================================================
# 1. DANE GEOMETRYCZNE ŚMIGŁA
# ============================================================
R = 0.250          # promień [m]
B = 2             # liczba łopat

# Stacje względne r/R
r_R_nodes = np.array([0.20, 0.35, 0.50, 0.65, 0.80, 0.95, 1.00])
c_nodes = np.array([35, 48, 50, 46, 38, 25, 12]) * 1e-3   # cięciwa [m]
beta_nodes = np.array([52, 36, 27, 21, 18, 15, 14])       # kąt skręcenia [°]
airfoil_names = ['NACA4415', 'NACA4412', 'NACA4412', 'NACA4410',
                 'NACA4409', 'NACA4408', 'NACA4408']

# Dyskretne promienie
r_nodes = r_R_nodes * R
N_nodes = len(r_nodes)

# Szerokości pierścieni (metoda trapezów)
dr = np.zeros(N_nodes)
dr[0] = (r_nodes[1] - r_nodes[0]) / 2.0
dr[-1] = (r_nodes[-1] - r_nodes[-2]) / 2.0
for i in range(1, N_nodes-1):
    dr[i] = (r_nodes[i+1] - r_nodes[i-1]) / 2.0

# ============================================================
# 2. WARUNKI PRACY
# ============================================================
RPM = 3000                 # obroty na minutę
omega = RPM * 2 * np.pi / 60.0   # prędkość kątowa [rad/s]

rho = 1.225                # gęstość powietrza [kg/m3]
mu = 1.81e-5               # lepkość dynamiczna [Pa·s]

# ============================================================
# 3. WCZYTYWANIE BIEGUNOWYCH Z PLIKÓW XFOIL
# ============================================================

def parse_xfoil_polar(filepath):
    """
    Wczytuje plik biegunowej XFOIL.
    Zwraca: (alpha_deg, cl, cd) jako numpy arrays, posortowane i bez duplikatów alpha.
    """
    with open(filepath, 'r') as f:
        lines = f.readlines()

    header_idx = None
    for i, line in enumerate(lines):
        if 'alpha' in line and 'CL' in line and 'CD' in line:
            header_idx = i
            break
    if header_idx is None:
        raise ValueError(f"Nie znaleziono nagłówka kolumn w pliku: {filepath}")

    data_start = header_idx + 1
    while data_start < len(lines) and '------' in lines[data_start]:
        data_start += 1

    alphas, cls, cds = [], [], []
    for line in lines[data_start:]:
        line = line.strip()
        if not line:          # pusta linia → koniec danych
            break
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            alpha = float(parts[0])
            cl = float(parts[1])
            cd = float(parts[2])
            alphas.append(alpha)
            cls.append(cl)
            cds.append(cd)
        except ValueError:
            continue

    alphas = np.array(alphas)
    cls = np.array(cls)
    cds = np.array(cds)

    if len(alphas) > 0:
        # Sortowanie według kąta natarcia alpha (wymóg dla interp1d)
        sort_idx = np.argsort(alphas)
        alphas = alphas[sort_idx]
        cls = cls[sort_idx]
        cds = cds[sort_idx]

        # Usunięcie ewentualnych duplikatów alpha
        alphas, unique_idx = np.unique(alphas, return_index=True)
        cls = cls[unique_idx]
        cds = cds[unique_idx]

    return alphas, cls, cds


def load_polars_from_folder(folder):
    """
    Przeszukuje wskazany folder w poszukiwaniu plików z biegunowymi (.dat / .txt).
    Nazwa pliku powinna być w formacie: NazwaProfilu_ReWartosc.rozszerzenie
    np. NACA4412_200000.dat lub NACA 4408_200000.dat.txt
    Spacje z nazwy profilu są usuwane, a nazwa konwertowana do wielkich liter.
    Zwraca słownik: raw_data[profile_name][Re] = (alpha, cl, cd)
    """
    raw_data = {}
    pattern = re.compile(r'^(.+?)_(\d+)\.(?:dat\.txt|dat|txt)$', re.IGNORECASE)

    if not os.path.exists(folder):
        raise FileNotFoundError(f"Folder stacji nie istnieje: {folder}")

    for filename in os.listdir(folder):
        match = pattern.match(filename)
        if not match:
            continue
        profile_raw = match.group(1)
        profile = profile_raw.replace(" ", "").upper()
        Re = int(match.group(2))
        filepath = os.path.join(folder, filename)

        alpha, cl, cd = parse_xfoil_polar(filepath)

        if profile not in raw_data:
            raw_data[profile] = {}
        raw_data[profile][Re] = (alpha, cl, cd)

    if not raw_data:
        raise FileNotFoundError(f"Nie znaleziono plikow z biegunowymi w folderze: {folder}")

    return raw_data


# Wczytywanie biegunowych dla każdej stacji ze specyficznych folderów "X R"
polars_by_station = []
for r_R in r_R_nodes:
    folder_name = f"{r_R:g} R"
    print(f"Wczytywanie biegunowych z folderu stacji: {folder_name}")
    station_polars = load_polars_from_folder(folder_name)
    polars_by_station.append(station_polars)

# ============================================================
# 4. INTERPOLACJA Cl(α, Re) i Cd(α, Re)
# ============================================================

def get_cl_cd(profile, Re, alpha_deg, station_polars):
    profile_key = profile.replace(" ", "").upper()
    if profile_key not in station_polars:
        raise ValueError(f"Brak danych dla profilu {profile_key} w folderze tej stacji.")

    re_list = sorted(station_polars[profile_key].keys())
    if Re <= re_list[0]:
        re_lo = re_hi = re_list[0]
    elif Re >= re_list[-1]:
        re_lo = re_hi = re_list[-1]
    else:
        for i in range(len(re_list)-1):
            if re_list[i] <= Re <= re_list[i+1]:
                re_lo = re_list[i]
                re_hi = re_list[i+1]
                break

    # Pobierz dane dla re_lo i re_hi
    alpha_lo, cl_lo, cd_lo = station_polars[profile_key][re_lo]
    alpha_hi, cl_hi, cd_hi = station_polars[profile_key][re_hi]

    interp_cl_lo = interp1d(alpha_lo, cl_lo, kind='linear', bounds_error=False,
                            fill_value=(cl_lo[0], cl_lo[-1]))
    interp_cd_lo = interp1d(alpha_lo, cd_lo, kind='linear', bounds_error=False,
                            fill_value=(cd_lo[0], cd_lo[-1]))
    if re_lo != re_hi:
        interp_cl_hi = interp1d(alpha_hi, cl_hi, kind='linear', bounds_error=False,
                                fill_value=(cl_hi[0], cl_hi[-1]))
        interp_cd_hi = interp1d(alpha_hi, cd_hi, kind='linear', bounds_error=False,
                                fill_value=(cd_hi[0], cd_hi[-1]))
        cl_lo_val = interp_cl_lo(alpha_deg)
        cl_hi_val = interp_cl_hi(alpha_deg)
        cd_lo_val = interp_cd_lo(alpha_deg)
        cd_hi_val = interp_cd_hi(alpha_deg)
        frac = (Re - re_lo) / (re_hi - re_lo)
        cl = cl_lo_val + frac * (cl_hi_val - cl_lo_val)
        cd = cd_lo_val + frac * (cd_hi_val - cd_lo_val)
    else:
        cl = interp_cl_lo(alpha_deg)
        cd = interp_cd_lo(alpha_deg)

    return cl, cd

# ============================================================
# 5. BEMT – ROZWIĄZANIE DLA POJEDYNCZEGO ELEMENTU (NA PODSTAWIE PHI)
# ============================================================

def solve_element_phi(r, chord, beta_deg, profile_name, Re_nominal, dr_elem, omega, V_inf, rho, mu, station_polars):
    """
    Rozwiązuje równanie BEMT dla pojedynczego elementu za pomocą metody zbieżności kąta dopływu (phi).
    Metoda ta eliminuje osobliwości przy zerowej prędkości lotu (V_inf = 0).
    Zwraca: a, ap, V_ax, dT, dQ
    """
    solidity = B * chord / (2 * np.pi * r)

    def residual(phi_val):
        sin_phi = np.sin(phi_val)
        cos_phi = np.cos(phi_val)
        alpha = beta_deg - np.degrees(phi_val)

        Cl, Cd = get_cl_cd(profile_name, Re_nominal, alpha, station_polars)

        # Poprawka Prandtla (straty brzegowe)
        f = (B / 2.0) * (R - r) / (r * sin_phi)
        if f > 100:
            F = 1.0
        else:
            F = (2.0 / np.pi) * np.arccos(np.exp(-f))
        F = max(F, 1e-6)

        term_cl = Cl * cos_phi - Cd * sin_phi
        term_cd = Cl * sin_phi + Cd * cos_phi

        # Wyznaczenie współczynnika indukcji obwodowej ap
        denom_ap = 4 * F * sin_phi * cos_phi / (solidity * term_cd) + 1.0
        ap = 1.0 / denom_ap if denom_ap > 0 else 0.0

        V_tan = omega * r * (1 - ap)
        W = V_tan / cos_phi
        dT_BEM = B * 0.5 * rho * (W**2) * chord * term_cl * dr_elem

        V_ax = V_tan * np.tan(phi_val)
        dT_mom = 4 * np.pi * r * rho * V_ax * (V_ax - V_inf) * F * dr_elem

        return dT_BEM - dT_mom

    # Poszukiwanie pierwiastka (bisekcja) w przedziale [0.01 deg, 89.9 deg]
    phi_low = np.radians(0.01)
    phi_high = np.radians(89.9)

    if residual(phi_low) * residual(phi_high) > 0:
        phi_sol = phi_low
    else:
        for _ in range(50):
            phi_mid = (phi_low + phi_high) / 2
            if residual(phi_mid) * residual(phi_low) <= 0:
                phi_high = phi_mid
            else:
                phi_low = phi_mid
        phi_sol = (phi_low + phi_high) / 2

    # Obliczenie końcowych wartości po znalezieniu zbieżnego kąta phi_sol
    sin_phi = np.sin(phi_sol)
    cos_phi = np.cos(phi_sol)
    alpha = beta_deg - np.degrees(phi_sol)
    Cl, Cd = get_cl_cd(profile_name, Re_nominal, alpha, station_polars)

    f = (B / 2.0) * (R - r) / (r * sin_phi)
    if f > 100:
        F = 1.0
    else:
        F = (2.0 / np.pi) * np.arccos(np.exp(-f))
    F = max(F, 1e-6)

    term_cl = Cl * cos_phi - Cd * sin_phi
    term_cd = Cl * sin_phi + Cd * cos_phi

    denom_ap = 4 * F * sin_phi * cos_phi / (solidity * term_cd) + 1.0
    ap = 1.0 / denom_ap if denom_ap > 0 else 0.0

    V_tan = omega * r * (1 - ap)
    W = V_tan / cos_phi
    V_ax = W * sin_phi

    if V_inf > 1e-5:
        a = 1.0 - V_ax / V_inf
    else:
        a = float('inf')

    dL_dr = 0.5 * rho * W**2 * chord * Cl
    dD_dr = 0.5 * rho * W**2 * chord * Cd

    dT = B * (dL_dr * np.cos(phi_sol) - dD_dr * np.sin(phi_sol)) * dr_elem
    dQ = B * (dL_dr * np.sin(phi_sol) + dD_dr * np.cos(phi_sol)) * r * dr_elem

    return a, ap, V_ax, dT, dQ


# ============================================================
# 6. PĘTLA PRĘDKOŚCI LOTU
# ============================================================
velocities = [0, 5, 10, 15, 20, 25, 30]

print("\nRozpoczynanie serii obliczeniowej dla roznych predkosci lotu...")

# Tablice do agregacji wyników podsumowujących
vel_list = []
T_list = []
Q_list = []
P_list = []
eta_list = []
CT_list = []
CP_list = []
J_list = []

# Lista do przechowywania szczegółowych wyników dla każdej prędkości (do wykresów porównawczych)
all_results = []

for V in velocities:
    folder_name = f"V_{V}"
    os.makedirs(folder_name, exist_ok=True)
    
    T_total = 0.0
    Q_total = 0.0
    results = []

    for i in range(N_nodes):
        profile = airfoil_names[i]
        r_local = r_nodes[i]
        chord = c_nodes[i]
        station_polars = polars_by_station[i]

        W0 = np.sqrt(V**2 + (omega * r_local)**2)
        Re_nominal = rho * W0 * chord / mu

        a, ap, V_ax, dT, dQ = solve_element_phi(
            r_local, chord, beta_nodes[i], profile, Re_nominal, dr[i],
            omega, V, rho, mu, station_polars
        )
        T_total += dT
        Q_total += dQ
        results.append((r_local, a, ap, V_ax, dT, dQ))

    # Zapamiętaj wyniki dla tej prędkości
    all_results.append({
        'V': V,
        'results': results.copy()
    })

    # Obliczenia globalne
    P = Q_total * omega
    eta = T_total * V / P if P > 0 else 0.0
    n = omega / (2 * np.pi)
    D = 2 * R

    CT = T_total / (rho * n**2 * D**4)
    CP = P / (rho * n**3 * D**5)
    J = V / (n * D)

    # Zapisanie wyników do list podsumowujących
    vel_list.append(V)
    T_list.append(T_total)
    Q_list.append(Q_total)
    P_list.append(P)
    eta_list.append(eta)
    CT_list.append(CT)
    CP_list.append(CP)
    J_list.append(J)

    # Zapis wyników tekstowych do pliku
    txt_filename = os.path.join(folder_name, f"wyniki_V_{V}.txt")
    with open(txt_filename, 'w') as f:
        f.write(f"====== WYNIKI OBLICZEN BEMT DLA V = {V} m/s ======\n")
        f.write(f"Ciag calkowity T = {T_total:.3f} N\n")
        f.write(f"Moment obrotowy Q = {Q_total:.3f} Nm\n")
        f.write(f"Moc pobierana P = {P:.3f} W\n")
        f.write(f"Sprawnosc smigla eta = {eta:.3f}\n")
        f.write(f"Wspolczynnik ciagu CT = {CT:.4f}\n")
        f.write(f"Wspolczynnik mocy CP = {CP:.4f}\n")
        f.write(f"Liczba postepu J = {J:.4f}\n\n")
        f.write("Szczegoly dla poszczegolnych stacji lopaty:\n")
        f.write("r/R   a          a'         V_ax[m/s]  dT[N]      dQ[Nm]\n")
        for res in results:
            r, a_val, ap_val, V_ax_val, dT_val, dQ_val = res
            a_str = f"{a_val:.4f}" if a_val != float('inf') else "   inf  "
            f.write(f"{r/R:.2f}  {a_str}     {ap_val:.4f}     {V_ax_val:8.3f}   {dT_val:8.4f}   {dQ_val:8.4f}\n")

    print(f"Predkosc V = {V:2d} m/s: T = {T_total:7.3f} N, Q = {Q_total:5.3f} Nm, P = {P:8.2f} W, eta = {eta:.3f} -> Zapisano w {folder_name}/")

    # ============================================================
    # 7. GENEROWANIE I ZAPIS WYKRESÓW DLA KAŻDEJ PRĘDKOŚCI
    # ============================================================
    r_R_vals = [res[0]/R for res in results]
    a_vals = [res[1] for res in results]
    ap_vals = [res[2] for res in results]
    V_ax_vals = [res[3] for res in results]
    dT_vals = [res[4] for res in results]
    dQ_vals = [res[5] for res in results]

    plt.rcParams['font.sans-serif'] = 'Arial'
    plt.rcParams['font.family'] = 'sans-serif'

    # Wykres 1: Indukcja
    fig1, ax1 = plt.subplots(figsize=(8, 5))
    if V > 0:
        ax1.plot(r_R_vals, a_vals, 'o-', color='#1f77b4', linewidth=2.5, label='Osiowy ($a$)')
        ax1.plot(r_R_vals, ap_vals, 's-', color='#ff7f0e', linewidth=2.5, label='Obwodowy ($a\'$)')
        ax1.set_ylabel('Wspolczynniki indukcji', fontsize=12, labelpad=8)
        ax1.set_title(f'Wspolczynniki indukcji wzdluż lopaty (V = {V} m/s)', fontsize=13, fontweight='bold', pad=15)
    else:
        ax1.plot(r_R_vals, V_ax_vals, '^-', color='#9467bd', linewidth=2.5, label='Predkosc osiowa $V_{ax}$')
        ax1.plot(r_R_vals, ap_vals, 's-', color='#ff7f0e', linewidth=2.5, label='Obwodowy ($a\'$)')
        ax1.set_ylabel('Prędkość [m/s] / Współczynnik', fontsize=12, labelpad=8)
        ax1.set_title(f'Predkosc osiowa i wsp. obwodowy (V = {V} m/s)', fontsize=13, fontweight='bold', pad=15)
    ax1.set_xlabel('Stacja wzgledna $r/R$', fontsize=12, labelpad=8)
    ax1.grid(True, linestyle='--', alpha=0.5)
    ax1.legend(fontsize=11, loc='best')
    fig1.tight_layout()
    fig1.savefig(os.path.join(folder_name, 'wspolczynniki_indukcji.png'), dpi=300)
    plt.close(fig1)

    # Wykres 2: Ciąg (dT)
    fig2, ax2 = plt.subplots(figsize=(8, 5))
    ax2.plot(r_R_vals, dT_vals, 'o-', color='#2ca02c', linewidth=2.5, label='Ciag elementu $dT$')
    ax2.set_xlabel('Stacja wzgledna $r/R$', fontsize=12, labelpad=8)
    ax2.set_ylabel('Ciag elementu $dT$ [N]', fontsize=12, labelpad=8)
    ax2.set_title(f'Rozklad sily ciagu (V = {V} m/s)', fontsize=13, fontweight='bold', pad=15)
    ax2.grid(True, linestyle='--', alpha=0.5)
    ax2.legend(fontsize=11, loc='best')
    fig2.tight_layout()
    fig2.savefig(os.path.join(folder_name, 'rozklad_ciagu.png'), dpi=300)
    plt.close(fig2)

    # Wykres 3: Moment (dQ)
    fig3, ax3 = plt.subplots(figsize=(8, 5))
    ax3.plot(r_R_vals, dQ_vals, 'o-', color='#d62728', linewidth=2.5, label='Moment elementu $dQ$')
    ax3.set_xlabel('Stacja wzgledna $r/R$', fontsize=12, labelpad=8)
    ax3.set_ylabel('Moment elementu $dQ$ [Nm]', fontsize=12, labelpad=8)
    ax3.set_title(f'Rozklad momentu obrotowego (V = {V} m/s)', fontsize=13, fontweight='bold', pad=15)
    ax3.grid(True, linestyle='--', alpha=0.5)
    ax3.legend(fontsize=11, loc='best')
    fig3.tight_layout()
    fig3.savefig(os.path.join(folder_name, 'rozklad_momentu.png'), dpi=300)
    plt.close(fig3)

# ============================================================
# 8. GENEROWANIE I ZAPIS WYKRESU PODSUMOWUJĄCEGO ORAZ DANYCH
# ============================================================
def generate_summary_plots(vel_list, T_list, Q_list, P_list, eta_list, CT_list, CP_list, J_list, output_filename="podsumowanie_wynikow.png"):
    # Zapis danych do pliku tekstowego
    txt_summary_filename = "podsumowanie_wynikow.txt"
    with open(txt_summary_filename, 'w') as f:
        f.write("====== ZBIORCZE PODSUMOWANIE WYNIKÓW BEMT ======\n")
        f.write(f"{'V [m/s]':>10} | {'T [N]':>10} | {'Q [Nm]':>10} | {'P [W]':>10} | {'eta [-]':>10} | {'CT [-]':>10} | {'CP [-]':>10} | {'J [-]':>10}\n")
        f.write("-" * 95 + "\n")
        for i in range(len(vel_list)):
            f.write(f"{vel_list[i]:10.2f} | {T_list[i]:10.3f} | {Q_list[i]:10.3f} | {P_list[i]:10.2f} | {eta_list[i]:10.3f} | {CT_list[i]:10.4f} | {CP_list[i]:10.4f} | {J_list[i]:10.4f}\n")
    print(f"\nDane podsumowujące zapisano do pliku: {os.path.abspath(txt_summary_filename)}")

    fig, axs = plt.subplots(1, 3, figsize=(16, 5))
    
    # Ciąg vs Prędkość
    axs[0].plot(vel_list, T_list, 'o-', color='#1f77b4', linewidth=2.5, markersize=8)
    axs[0].set_xlabel('Prędkość lotu $V$ [m/s]', fontsize=11, labelpad=5)
    axs[0].set_ylabel('Ciąg całkowity $T$ [N]', fontsize=11, labelpad=5)
    axs[0].set_title('Ciąg w funkcji prędkości lotu', fontsize=12, fontweight='bold')
    axs[0].grid(True, linestyle='--', alpha=0.5)
    
    # Moc vs Prędkość
    axs[1].plot(vel_list, P_list, 'o-', color='#d62728', linewidth=2.5, markersize=8)
    axs[1].set_xlabel('Prędkość lotu $V$ [m/s]', fontsize=11, labelpad=5)
    axs[1].set_ylabel('Moc pobierana $P$ [W]', fontsize=11, labelpad=5)
    axs[1].set_title('Moc w funkcji prędkości lotu', fontsize=12, fontweight='bold')
    axs[1].grid(True, linestyle='--', alpha=0.5)
    
    # Sprawność vs Prędkość
    axs[2].plot(vel_list, eta_list, 'o-', color='#2ca02c', linewidth=2.5, markersize=8)
    axs[2].set_xlabel('Prędkość lotu $V$ [m/s]', fontsize=11, labelpad=5)
    axs[2].set_ylabel(r'Sprawnosc smigla $\eta$', fontsize=11, labelpad=5)
    axs[2].set_title('Sprawność w funkcji prędkości lotu', fontsize=12, fontweight='bold')
    axs[2].grid(True, linestyle='--', alpha=0.5)
    axs[2].set_ylim(-0.05, 1.05)
    
    fig.suptitle('ZBIORCZA CHARAKTERYSTYKA PRACY ŚMIGŁA (BEMT)', fontsize=15, fontweight='bold', y=1.05)
    fig.tight_layout()
    fig.savefig(output_filename, dpi=300, bbox_inches='tight')
    print(f"Wykres podsumowujący został zapisany jako: {os.path.abspath(output_filename)}")
    
    try:
        plt.show()
    except Exception:
        pass

generate_summary_plots(vel_list, T_list, Q_list, P_list, eta_list, CT_list, CP_list, J_list, "podsumowanie_wynikow.png")

# ============================================================
# 9. PORÓWNAWCZE WYKRESY ROZKŁADÓW DLA WSZYSTKICH PRĘDKOŚCI
# ============================================================
plt.rcParams['font.sans-serif'] = 'Arial'
plt.rcParams['font.family'] = 'sans-serif'

# Kolory dla różnych prędkości
colors = plt.cm.viridis(np.linspace(0, 1, len(velocities)))

# --- Wykres porównawczy współczynnika indukcji a ---
fig_a, ax_a = plt.subplots(figsize=(10, 6))
for i, data in enumerate(all_results):
    V = data['V']
    res = data['results']
    r_R_vals = [r/R for r, a, ap, Vax, dT, dQ in res]
    a_vals = [a if a != float('inf') else np.nan for r, a, ap, Vax, dT, dQ in res]
    ax_a.plot(r_R_vals, a_vals, 'o-', color=colors[i], linewidth=2, label=f'V = {V} m/s')

ax_a.set_xlabel('Stacja względna $r/R$', fontsize=12)
ax_a.set_ylabel('Współczynnik indukcji osiowej $a$', fontsize=12)
ax_a.set_title('Porównanie rozkładu współczynnika $a$ dla różnych prędkości lotu', fontsize=13, fontweight='bold')
ax_a.grid(True, linestyle='--', alpha=0.5)
ax_a.legend(fontsize=10, loc='best')
fig_a.tight_layout()
fig_a.savefig('porownanie_a.png', dpi=300)
print("Zapisano porownanie_a.png")

# --- Wykres porównawczy siły ciągu dT ---
fig_dT, ax_dT = plt.subplots(figsize=(10, 6))
for i, data in enumerate(all_results):
    V = data['V']
    res = data['results']
    r_R_vals = [r/R for r, a, ap, Vax, dT, dQ in res]
    dT_vals = [dT for r, a, ap, Vax, dT, dQ in res]
    ax_dT.plot(r_R_vals, dT_vals, 'o-', color=colors[i], linewidth=2, label=f'V = {V} m/s')

ax_dT.set_xlabel('Stacja względna $r/R$', fontsize=12)
ax_dT.set_ylabel('Siła ciągu elementu $dT$ [N]', fontsize=12)
ax_dT.set_title('Porównanie rozkładu ciągu $dT$ dla różnych prędkości lotu', fontsize=13, fontweight='bold')
ax_dT.grid(True, linestyle='--', alpha=0.5)
ax_dT.legend(fontsize=10, loc='best')
fig_dT.tight_layout()
fig_dT.savefig('porownanie_dT.png', dpi=300)
print("Zapisano porownanie_dT.png")

# --- Wykres porównawczy momentu dQ ---
fig_dQ, ax_dQ = plt.subplots(figsize=(10, 6))
for i, data in enumerate(all_results):
    V = data['V']
    res = data['results']
    r_R_vals = [r/R for r, a, ap, Vax, dT, dQ in res]
    dQ_vals = [dQ for r, a, ap, Vax, dT, dQ in res]
    ax_dQ.plot(r_R_vals, dQ_vals, 'o-', color=colors[i], linewidth=2, label=f'V = {V} m/s')

ax_dQ.set_xlabel('Stacja względna $r/R$', fontsize=12)
ax_dQ.set_ylabel('Moment elementu $dQ$ [Nm]', fontsize=12)
ax_dQ.set_title('Porównanie rozkładu momentu $dQ$ dla różnych prędkości lotu', fontsize=13, fontweight='bold')
ax_dQ.grid(True, linestyle='--', alpha=0.5)
ax_dQ.legend(fontsize=10, loc='best')
fig_dQ.tight_layout()
fig_dQ.savefig('porownanie_dQ.png', dpi=300)
print("Zapisano porownanie_dQ.png")

plt.close('all')
print("\nWszystkie obliczenia i generowanie podsumowania ukończone pomyślnie!")