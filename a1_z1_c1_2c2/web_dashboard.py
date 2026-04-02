import asyncio
from fastapi import FastAPI, Request, Response, Form, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
import aiosqlite
import io
import os
import time
import logging
from jinja2 import Template
from fastapi.staticfiles import StaticFiles
from config import settings

app = FastAPI(title="Mogosu v9 Ultimate")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")
app.state.bot = None

# Secure PIN from env or default
DASHBOARD_PIN = os.getenv("DASHBOARD_PIN", "7777")

def is_authenticated(request: Request):
    return request.cookies.get("admin_session") == DASHBOARD_PIN

@app.post("/login")
async def login(pin: str = Form(...)):
    if pin == DASHBOARD_PIN:
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="admin_session", value=DASHBOARD_PIN, httponly=True, max_age=86400)
        return response
    return {"status": "error", "message": "Invalid PIN"}

@app.get("/")
async def index(request: Request):
    if not is_authenticated(request):
        return HTMLResponse(LOGIN_HTML)
    return HTMLResponse(TEMPLATES_HTML)

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Mogosu | Auth</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-[#050508] flex items-center justify-center h-screen">
    <form action="/login" method="post" class="glass p-8 bg-gray-900 rounded-2xl border border-white/10 w-80">
        <h1 class="text-2xl font-black mb-6 text-center">ACCESS PIN</h1>
        <input type="password" name="pin" class="w-full p-3 bg-black rounded-xl border border-white/10 text-center text-xl mb-4" placeholder="****" required>
        <button type="submit" class="w-full bg-blue-600 py-3 rounded-xl font-bold">UNLOCK</button>
    </form>
</body>
</html>
"""

TEMPLATES_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>⚡ MOGOSU ADMIN COMMAND CENTER</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #060609; color: #fff; overscroll-behavior: none; }
        .glass { background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 24px; padding: 1.5rem; }
        .nav-btn { transition: all 0.2s; border-radius: 12px; }
        .active-tab { background: #3b82f6 !important; color: #fff !important; box-shadow: 0 4px 15px rgba(59, 130, 246, 0.3); }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .scrollbar-hide::-webkit-scrollbar { display: none; }
        @keyframes fadeUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .nav-btn { transition: all 0.2s; position: relative; }
        .nav-btn:hover { color: #fff; }
        .cat-card { transition: all 0.3s; border: 1px solid rgba(255,255,255,0.03); }
        .cat-card:hover { border-color: rgba(59, 130, 246, 0.4); transform: translateY(-2px); }
        .btn-fancy { background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); transition: transform 0.2s; }
        .btn-fancy:active { transform: scale(0.95); }
        .stock-badge { background: linear-gradient(135deg, #10b981 0%, #059669 100%); }
        .empty-badge { background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); }
        /* Fix for SweetAlert inputs displaying white on white */
        .swal2-input, .swal2-select, .swal2-textarea {
            background-color: #1a1a24 !important;
            color: #ffffff !important;
            border: 1px solid rgba(255,255,255,0.1) !important;
        }
        .swal2-input::placeholder { color: rgba(255,255,255,0.3) !important; }
        .swal2-html-container { color: #ccc !important; }
    </style>
</head>
<body class="p-4 md:p-10">
    <div class="max-w-7xl mx-auto">
        <header class="flex flex-col md:flex-row justify-between items-center mb-8 md:mb-16 gap-6">
            <div class="flex items-center gap-4">
               <div class="w-10 h-10 md:w-12 md:h-12 bg-blue-600 rounded-full flex items-center justify-center shadow-lg shadow-blue-500/20">
                   <i class="fas fa-crown text-white"></i>
               </div>
               <h1 class="text-3xl md:text-4xl font-black italic tracking-tighter">MOGOSU <span class="text-blue-500">ADMIN</span></h1>
            </div>
            <div class="flex flex-col md:flex-row items-center gap-6">
                <div class="hidden lg:flex items-center gap-2 bg-white/5 px-4 py-2 rounded-xl border border-white/5">
                    <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                    <span class="text-[10px] font-mono font-bold text-blue-300" id="live-clock">--:--:--</span>
                </div>
                <div class="flex p-1 bg-white/5 rounded-xl md:rounded-2xl w-full md:w-auto overflow-x-auto scrollbar-hide">
                    <button onclick="switchTab('overview')" id="tab-overview" class="nav-btn active-tab flex-1 md:flex-none px-4 md:px-6 py-2.5 md:py-3 font-bold text-gray-500 text-[10px] md:text-sm uppercase tracking-wider whitespace-nowrap">PANOU</button>
                    <button onclick="switchTab('store')" id="tab-store" class="nav-btn flex-1 md:flex-none px-4 md:px-6 py-2.5 md:py-3 font-bold text-gray-500 text-[10px] md:text-sm uppercase tracking-wider whitespace-nowrap">MAGAZIN</button>
                    <button onclick="switchTab('wallets')" id="tab-wallets" class="nav-btn flex-1 md:flex-none px-4 md:px-6 py-2.5 md:py-3 font-bold text-gray-500 text-[10px] md:text-sm uppercase tracking-wider whitespace-nowrap">PORTOFELE</button>
                    <button onclick="switchTab('users')" id="tab-users" class="nav-btn flex-1 md:flex-none px-4 md:px-6 py-2.5 md:py-3 font-bold text-gray-500 text-[10px] md:text-sm uppercase tracking-wider whitespace-nowrap">UTILIZATORI</button>
                </div>
            </div>
        </header>

        <!-- Overview Section -->
        <div id="overview" class="tab-content active">
            <!-- Row 1: Stat Cards (Premium Layout) -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-10">
                <div class="bg-gradient-to-br from-blue-600/10 to-transparent p-8 rounded-3xl border border-white/5 relative overflow-hidden group">
                    <div class="text-[10px] text-gray-500 uppercase font-black tracking-widest mb-4">Venit Net</div>
                    <div class="text-3xl font-black text-blue-500 mb-1" id="stat-revenue">0 RON</div>
                    <div class="text-[9px] text-blue-900 font-bold uppercase">Bani curățați din Matrix</div>
                    <div class="absolute -right-4 -bottom-4 opacity-5 transform rotate-12 group-hover:scale-110 transition-transform">
                        <i class="fas fa-chart-line text-8xl text-white"></i>
                    </div>
                </div>
                <div class="bg-gradient-to-br from-white/5 to-transparent p-8 rounded-3xl border border-white/5 relative overflow-hidden group">
                    <div class="text-[10px] text-gray-500 uppercase font-black tracking-widest mb-4">Vânzări Totale</div>
                    <div class="text-3xl font-black text-white mb-1" id="stat-sales">0</div>
                    <div class="text-[9px] text-gray-700 font-bold uppercase">Tranzacții Finalizate</div>
                </div>
                <div class="bg-gradient-to-br from-yellow-500/10 to-transparent p-8 rounded-3xl border border-white/5 relative overflow-hidden group">
                    <div class="text-[10px] text-gray-500 uppercase font-black tracking-widest mb-4">În Așteptare</div>
                    <div class="text-3xl font-black text-yellow-500 mb-1" id="stat-pending">0</div>
                    <div class="text-[9px] text-yellow-900 font-bold uppercase">Comenzi ce așteaptă confirmarea</div>
                </div>
                <div class="bg-gradient-to-br from-green-500/10 to-transparent p-8 rounded-3xl border border-white/5 relative overflow-hidden group">
                    <div class="text-[10px] text-gray-500 uppercase font-black tracking-widest mb-4">Activ Acum</div>
                    <div class="text-3xl font-black text-green-400 mb-1" id="stat-online">0</div>
                    <div class="text-[9px] text-green-900 font-bold uppercase whitespace-nowrap animate-pulse">Entități active în sistem</div>
                    <div class="absolute top-4 right-4">
                        <div class="w-1.5 h-1.5 bg-green-500 rounded-full"></div>
                    </div>
                </div>
            </div>

            <!-- Row 2: Secondary Info & Activity -->
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <!-- Activity Stream (Left 2/3) -->
                <div class="lg:col-span-2 glass !p-6 md:!p-10 border-white/10 shadow-2xl">
                    <div class="flex justify-between items-center mb-10">
                        <h3 class="text-2xl font-black italic uppercase tracking-tighter">Flux Activitate Direct</h3>
                        <div class="flex items-center gap-3">
                             <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse shadow-lg shadow-blue-500/50"></div>
                             <span class="text-[10px] font-black uppercase text-blue-500 tracking-widest">Sistem Activ</span>
                        </div>
                    </div>
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4" id="recent-ops">
                        <div class="text-gray-800 text-xs italic sm:col-span-2">Se conectează la rețea...</div>
                    </div>
                </div>

                <!-- Right Side: Protocol Summary -->
                <div class="space-y-6">
                    <div class="glass p-8 border-l-4 border-l-blue-500">
                        <h4 class="text-[10px] font-black uppercase tracking-widest text-gray-700 mb-6 flex items-center gap-2">
                             <i class="fas fa-server"></i>
                             Status Operațional Seif
                        </h4>
                        <div class="grid grid-cols-2 gap-8">
                             <div>
                                 <div id="dash-stock" class="text-3xl font-black italic text-white line-height-1">0</div>
                                 <div class="text-[9px] font-bold text-gray-500 uppercase mt-1 tracking-tighter">Produse în Stoc</div>
                             </div>
                             <div>
                                 <div id="dash-addresses" class="text-3xl font-black italic text-blue-500 line-height-1">0</div>
                                 <div class="text-[9px] font-bold text-gray-500 uppercase mt-1 tracking-tighter">Receptoare Plată (LTC)</div>
                             </div>
                        </div>
                        <div class="mt-8 pt-8 border-t border-white/5 space-y-4">
                             <div class="flex items-center gap-4">
                                 <div class="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center text-blue-400">
                                     <i class="fas fa-microchip text-[12px]"></i>
                                 </div>
                                 <div class="flex-1">
                                     <div class="flex justify-between text-[11px] mb-1 font-bold">
                                         <span class="text-gray-500 uppercase">Stare Sistem</span>
                                         <span class="text-white">STABIL</span>
                                     </div>
                                     <div class="w-full h-1 bg-white/5 rounded-full overflow-hidden">
                                         <div class="bg-blue-500 h-full w-[95%]"></div>
                                     </div>
                                 </div>
                             </div>
                        </div>
                    </div>

                    <div class="bg-white/[0.02] border border-white/5 p-6 rounded-2xl">
                        <h4 class="text-[10px] font-black uppercase tracking-widest text-gray-500 mb-4 italic">Acțiuni Rapide</h4>
                        <div class="grid grid-cols-2 gap-2">
                             <button onclick="switchTab('store')" class="bg-white/5 p-3 rounded-lg text-[9px] font-bold uppercase hover:bg-white/10 transition-colors">Admin Magazin</button>
                             <button onclick="switchTab('users')" class="bg-white/5 p-3 rounded-lg text-[9px] font-bold uppercase hover:bg-white/10 transition-colors">Verifică Useri</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Wallets Section -->
        <div id="wallets" class="tab-content">
            <div class="flex justify-between items-center mb-10">
                <div>
                    <h3 class="text-2xl font-black italic uppercase tracking-tight">Rezervă Litecoin</h3>
                    <p class="text-[10px] text-gray-600 font-bold uppercase tracking-widest mt-1">Sistem Rotație Adrese</p>
                </div>
                <button onclick="addAddress()" class="bg-blue-600 px-6 py-3 rounded-xl text-xs font-black uppercase shadow-lg shadow-blue-500/20">Leagă Adresă Nouă</button>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6" id="address-list">
            </div>
        </div>

        <!-- Store Section -->
        <div id="store" class="tab-content">
            <div class="flex flex-col md:flex-row justify-between items-center mb-8 gap-4">
                <h2 class="text-4xl font-black italic uppercase tracking-tighter">Gestiune Produse</h2>
                <div class="flex gap-4">
                    <button onclick="createCategory()" class="bg-white/5 border border-white/10 px-6 py-2.5 rounded-xl font-bold text-xs hover:bg-white/10 transition-all">+ CAT</button>
                    <button onclick="createItem()" class="btn-fancy px-6 py-2.5 rounded-xl font-bold text-xs shadow-xl shadow-blue-500/20">+ PRODUS</button>
                </div>
            </div>
            <div id="category-menu" class="grid grid-cols-2 md:grid-cols-3 gap-4 mb-12"></div>
            <div id="store-grid" class="space-y-12"></div>
        </div>

        <!-- Users Section -->
        <div id="users" class="tab-content">
            <h2 class="text-4xl font-black italic uppercase mb-12 tracking-tighter">Baza de Utilizatori</h2>
            <div id="user-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"></div>
        </div>
    </div>

    <script>
        async function switchTab(id) {
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active-tab'));
            document.getElementById(id).classList.add('active');
            const tabBtn = document.getElementById('tab-' + id);
            if(tabBtn) tabBtn.classList.add('active-tab');

            if (id === 'store') loadStore();
            if (id === 'users') loadUsers();
            if (id === 'wallets') loadAddresses();
            if (id === 'overview') loadOps();
        }

        let activeCategoryId = null;

        async function loadStore() {
            try {
                const res = await fetch('/api/inventory');
                if (res.status === 403) { window.location.reload(); return; }
                const data = await res.json();
                
                if (!data.categories || data.categories.length === 0) {
                     document.getElementById('category-menu').innerHTML = '<div class="col-span-full text-center p-8 text-gray-800 font-black uppercase">Neutral Matrix: No sectors established</div>';
                     return;
                }

                // Render 3x3 Category Menu
                const menu = document.getElementById('category-menu');
                menu.innerHTML = data.categories.map(cat => {
                    const itemsInCat = data.items.filter(i => i.category_id === cat.id);
                    const totalStock = itemsInCat.reduce((sum, i) => sum + i.stock_count, 0);
                    const isActive = activeCategoryId === cat.id;
                    const isAvailable = totalStock > 0;
                    
                    const statusClass = isAvailable ? 'border-green-500/30' : 'border-red-500/30';
                    const activeClass = isActive ? 'bg-blue-600 border-blue-500 shadow-xl shadow-blue-500/20 scale-95' : 'bg-white/[0.02] border-white/5 hover:bg-white/[0.05]';
                    
                    return `
                    <div onclick="selectCategory(${cat.id})" class="cursor-pointer group flex flex-col items-center justify-center p-6 rounded-3xl border transition-all ${statusClass} ${activeClass}">
                        <div class="text-5xl mb-2 group-hover:scale-110 transition-transform">${cat.name}</div>
                        <div class="h-1.5 w-1.5 rounded-full ${isAvailable ? 'bg-green-500 animate-pulse' : 'bg-red-500'}"></div>
                    </div>
                    `;
                }).join('');

                // Render Item display
                const storeGrid = document.getElementById('store-grid');
                if (!activeCategoryId) {
                    storeGrid.innerHTML = '<div class="text-center p-20 glass text-gray-700 italic font-black uppercase tracking-widest border-dashed">Selectează un sector pentru a vedea inventarul</div>';
                } else {
                    renderSelectedCategory(data);
                }
            } catch (e) {
                console.error("Matrix Sync Error:", e);
            }
        }

        function renderSelectedCategory(data) {
            const cat = data.categories.find(c => c.id === activeCategoryId);
            const items = data.items.filter(i => i.category_id === activeCategoryId);
            const storeGrid = document.getElementById('store-grid');
            
            storeGrid.innerHTML = `
                <div class="glass p-2 cat-card mb-8">
                    <div class="p-8 pb-4 flex justify-between items-center">
                        <div class="flex items-center gap-4">
                           <div class="text-4xl">${cat.name}</div>
                           <div class="flex flex-col">
                               <h3 class="text-2xl font-black italic text-blue-500 uppercase tracking-tighter">Sector Operațional</h3>
                               <p class="text-[9px] text-gray-700 font-bold uppercase tracking-widest mt-1">Sincronizat și Securizat</p>
                           </div>
                        </div>
                        <button onclick="activeCategoryId=null; loadStore();" class="text-[10px] font-black text-gray-600 hover:text-white uppercase tracking-widest">ÎNCHIDE SECTOR [X]</button>
                    </div>
                    <div class="p-8 pt-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                        ${items.map(item => {
                            const isAvail = item.stock_count > 0;
                            const badgeColor = isAvail ? 'bg-green-600' : 'bg-red-600';
                            const titleColor = isAvail ? 'text-green-400' : 'text-red-400';
                            const ltcPrice = (item.price_ron / 300.0).toFixed(4);
                            return `
                            <div class="p-8 glass bg-white/[0.02] border border-white/5 rounded-3xl group/item hover:border-blue-500/40 hover:shadow-2xl hover:shadow-blue-500/5 transition-all">
                                <div class="flex justify-between items-start mb-6">
                                    <h4 class="text-xl font-black italic ${titleColor} transition-colors">${item.name}</h4>
                                    <span class="${badgeColor} text-[9px] font-black text-white px-3 py-1.5 rounded-lg shadow-sm uppercase">${item.stock_count} ÎN STOC</span>
                                </div>
                                <p class="text-sm text-gray-500 mb-8 italic leading-relaxed line-clamp-2 h-10">${item.description || 'Nicio descriere disponibilă în Matrix.'}</p>
                                <div class="flex flex-col gap-6">
                                    <div class="flex justify-between items-end">
                                        <div class="flex flex-col">
                                            <span class="text-blue-500 font-black text-xl">${item.price_ron} <span class="text-[10px] uppercase">RON</span></span>
                                            <span class="text-gray-700 font-bold text-[9px] uppercase tracking-tighter">${ltcPrice} LTC RECEPTOR</span>
                                        </div>
                                        <div class="flex gap-2">
                                            <button onclick="addStock(${item.id}); event.stopPropagation();" class="bg-blue-600/10 text-blue-500 hover:bg-blue-600 hover:text-white px-6 py-2 rounded-xl font-black text-[10px] uppercase transition-all shadow-lg hover:shadow-blue-500/20" title="Alimentează Stoc Matrix">+ ADĂUGARE SECRET</button>
                                        </div>
                                    </div>
                                    ${item.stock_count > 0 ? `
                                        <div class="grid grid-cols-5 gap-2 pt-4 border-t border-white/5">
                                            ${item.stock.slice(0, 5).map(s => `
                                                <div class="relative group/s">
                                                    <div class="w-full aspect-square bg-white/5 rounded-lg border border-white/10 flex items-center justify-center overflow-hidden">
                                                        <i class="fas fa-file-image text-gray-800 text-[10px]"></i>
                                                    </div>
                                                    <button onclick="burnStock(${s.id}); event.stopPropagation();" class="absolute -top-1 -right-1 bg-red-500 rounded-full w-4 h-4 flex items-center justify-center text-[8px] opacity-0 group-hover/s:opacity-100 transition-opacity"><i class="fas fa-times"></i></button>
                                                </div>
                                            `).join('')}
                                        </div>
                                    ` : ''}
                                </div>
                            </div>
                        `}).join('')}
                    </div>
                </div>`;
        }

        function selectCategory(id) {
            activeCategoryId = (activeCategoryId === id) ? null : id;
            loadStore();
        }

        async function killItem(id) {
            const confirmed = await Swal.fire({
                title: 'Elimină Produsul?',
                text: "Această acțiune va șterge definitiv produsul și tot stocul aferent.",
                icon: 'warning',
                background: '#111', color: '#fff',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                confirmButtonText: 'ȘTERGE',
                cancelButtonText: 'ANULEAZĂ'
            });
            if(confirmed.isConfirmed) {
                await fetch(`/api/items/${id}`, { method: 'DELETE' });
                loadStore();
            }
        }

        async function burnStock(id) {
             await fetch(`/api/stock/${id}`, { method: 'DELETE' });
             loadStore();
        }

        async function addStock(itemId) {
            const { value: formValues } = await Swal.fire({
                title: 'Adăugare Stoc Matrix',
                html: 
                    '<div class="flex flex-col gap-4 text-left p-2">' +
                        '<label class="text-[10px] font-black text-blue-500 uppercase tracking-widest px-1">Încarcă Produs (Poză/Video/GIF)</label>' +
                        '<input id="swal-file" type="file" class="swal2-input m-0 w-full" style="padding: 10px;">' +
                        '<label class="text-[10px] font-black text-gray-500 uppercase tracking-widest px-1 mt-4">Descriere Secretă / Mesaj de Livrare</label>' +
                        '<textarea id="swal-caption" class="swal2-input m-0 w-full h-24" placeholder="Ex: Detalii cont, link sau mesaj secret"></textarea>' +
                    '</div>',
                focusConfirm: false,
                background: '#0d0d12', color: '#fff',
                width: '500px',
                confirmButtonText: 'LIVREAZĂ ÎN MATRIX',
                customClass: { confirmButton: 'btn-fancy px-10 py-3 rounded-xl' },
                preConfirm: () => {
                    return {
                        file: document.getElementById('swal-file').files[0],
                        caption: document.getElementById('swal-caption').value
                    }
                }
            });
            
            if (formValues && (formValues.file || formValues.caption)) {
                const form = new FormData();
                form.append('item_id', itemId);
                if (formValues.file) {
                    form.append('file', formValues.file);
                    // Automatic media type detection
                    const ext = formValues.file.name.split('.').pop().toLowerCase();
                    if (['mp4', 'mov', 'avi'].includes(ext)) form.append('media_type', 'video');
                    else if (['gif'].includes(ext)) form.append('media_type', 'animation');
                    else form.append('media_type', 'photo');
                } else {
                    form.append('media_type', 'text');
                }
                form.append('caption', formValues.caption);
                
                Swal.fire({ title: 'Se procesează...', allowOutsideClick: false, didOpen: () => Swal.showLoading() });
                
                try {
                    await fetch('/api/stock', { method: 'POST', body: form });
                    Swal.fire({ icon: 'success', title: 'Stoc Livrat', background: '#0d0d12', color: '#fff', timer: 1500 });
                    loadStore();
                } catch (e) {
                    Swal.fire({ icon: 'error', title: 'Eroare Încărcare', background: '#0d0d12', color: '#fff' });
                }
            }
        }

        async function loadAddresses() {
            const res = await fetch('/api/addresses');
            const data = await res.json();
            const list = document.getElementById('address-list');
            list.innerHTML = data.addresses.map(a => {
                const isBusy = a.in_use_by_sale_id != null;
                const statusColor = isBusy ? 'text-yellow-500 bg-yellow-500/10 border-yellow-500/20' : 'text-green-500 bg-green-500/10 border-green-500/20';
                return `
                <div class="bg-white/[0.02] border border-white/5 p-6 rounded-2xl relative overflow-hidden group">
                    <div class="flex justify-between items-start mb-6">
                        <div class="p-3 bg-white/5 rounded-xl">
                            <i class="fas fa-wallet text-blue-500"></i>
                        </div>
                        <span class="px-3 py-1 rounded-full border text-[9px] font-black uppercase ${statusColor}">${isBusy ? 'SESIUNE ACTIVĂ' : 'GATA / DISPONIBIL'}</span>
                    </div>
                    <div class="space-y-4">
                        <div class="text-[10px] text-gray-700 font-bold uppercase tracking-widest">Adresă Receptor</div>
                        <div onclick="editAddress(${a.id}, '${a.crypto_address}')" class="text-sm font-mono text-white cursor-pointer hover:text-blue-500 block truncate transition-colors">${a.crypto_address}</div>
                    </div>
                    <div class="mt-8 pt-6 border-t border-white/5 flex justify-between items-center">
                        <span class="text-[8px] font-black text-gray-800 uppercase italic">Creat: ${a.created_at || 'Mog_Init'}</span>
                        <button onclick="deleteAddress(${a.id}); event.stopPropagation();" class="text-red-900 border border-red-900/20 hover:bg-red-900 hover:text-white px-3 py-1 rounded-lg text-[8px] font-black uppercase transition-all">Deconectează</button>
                    </div>
                </div>
            `}).join('');
        }

        async function editAddress(id, currentAddr) {
            const { value: newAddr } = await Swal.fire({
                title: 'Editează Adresa Receptor',
                input: 'text',
                inputValue: currentAddr,
                inputLabel: 'Adresă nouă LTC',
                background: '#0d0d12', color: '#fff',
                confirmButtonText: 'ACTUALIZEAZĂ',
                customClass: { confirmButton: 'btn-fancy px-8 py-2 rounded-lg' }
            });
            if (newAddr && newAddr !== currentAddr) {
                const form = new FormData();
                form.append('address', newAddr);
                await fetch(`/api/addresses/${id}`, { method: 'PUT', body: form });
                Swal.fire({ icon: 'success', title: 'Adresă Actualizată', background: '#0d0d12', color: '#fff', timer: 1000 });
                loadAddresses();
            }
        }

        async function addAddress() {
            const { value: address } = await Swal.fire({
                title: 'Leagă Adresă LTC Nouă',
                input: 'text',
                inputLabel: 'Adresa portofelului Litecoin',
                inputPlaceholder: 'Introdu adresa LTC...',
                background: '#0d0d12', color: '#fff',
                confirmButtonText: 'LEAGĂ ADRESA',
                customClass: { confirmButton: 'btn-fancy px-8 py-2 rounded-lg' }
            });
            if (address) {
                const form = new FormData();
                form.append('address', address);
                await fetch('/api/addresses', { method: 'POST', body: form });
                loadAddresses();
            }
        }

        async function deleteAddress(id) {
            const confirmed = await Swal.fire({
                title: 'Ești sigur?',
                text: "Vrei să deconectezi acest receptor de la Matrix?",
                icon: 'warning',
                showCancelButton: true,
                background: '#0d0d12', color: '#fff',
                confirmButtonColor: '#d33',
                confirmButtonText: 'DA, ȘTERGE'
            });
            if (confirmed.isConfirmed) {
                await fetch('/api/addresses/' + id, { method: 'DELETE' });
                loadAddresses();
            }
        }


        async function loadUsers() {
            const res = await fetch('/api/users');
            const data = await res.json();
            document.getElementById('user-grid').innerHTML = data.users.map(u => `
                <div onclick="showUserVault(${u.telegram_id})" class="cursor-pointer glass p-6 flex flex-col gap-6 group hover:border-blue-500/30 transition-all hover:scale-[1.02]">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-4">
                            <img src="${u.profile_photo ? '/' + u.profile_photo : 'https://api.dicebear.com/7.x/bottts/svg?seed=' + u.telegram_id}" class="w-12 h-12 rounded-2xl object-cover border border-white/10 shadow-lg group-hover:border-blue-500/40 transition-colors">
                            <div>
                                <div class="font-black italic text-lg truncate w-32">@${u.username || 'ANON'}</div>
                                <div class="text-[10px] text-gray-700 font-mono font-black">${u.telegram_id}</div>
                            </div>
                        </div>
                        <button onclick="abortUser(${u.telegram_id})" class="w-10 h-10 bg-red-500/5 text-red-900 border border-red-500/10 hover:bg-red-500 hover:text-white rounded-xl transition-all" title="ABORT FLOW">
                             <i class="fas fa-power-off text-sm"></i>
                        </button>
                    </div>
                    <div class="flex justify-between items-center bg-black/20 p-3 rounded-xl border border-white/[0.03]">
                        <div class="text-[9px] font-black uppercase text-gray-500 tracking-tighter">Protocol Entry</div>
                        <div class="text-[9px] font-mono text-blue-500 font-black">${u.joined_at}</div>
                    </div>
                </div>
            `).join('');
        }

        async function showUserVault(tgId) {
            Swal.fire({ title: 'Sincronizare Profil...', background: '#0d0d12', color: '#fff', didOpen: () => Swal.showLoading() });
            try {
                const res = await fetch(`/api/user-profile/${tgId}`);
                const data = await res.json();
                
                const pfp = data.user.profile_photo ? '/' + data.user.profile_photo : 'https://api.dicebear.com/7.x/bottts/svg?seed=' + tgId;
                
                Swal.fire({
                    width: '800px',
                    background: '#0d0d12',
                    color: '#fff',
                    showConfirmButton: false,
                    showCloseButton: true,
                    html: `
                        <div class="text-left">
                            <div class="flex items-center gap-6 mb-10 pb-8 border-b border-white/10">
                                <img src="${pfp}" class="w-24 h-24 rounded-[32px] object-cover border-4 border-blue-600/20 shadow-2xl">
                                <div class="flex-1">
                                    <div class="flex justify-between items-start">
                                        <div>
                                            <h2 class="text-3xl font-black italic uppercase tracking-tighter">@${data.user.username || 'Anonim'}</h2>
                                            <p class="text-blue-500 font-mono font-black text-xs">ID_ENTITATE: ${tgId}</p>
                                        </div>
                                        <button onclick="abortUser(${tgId})" class="bg-red-600/10 text-red-500 border border-red-500/20 px-4 py-2 rounded-xl font-black text-[10px] uppercase hover:bg-red-600 hover:text-white transition-all">Resetează Flow</button>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="grid grid-cols-2 gap-8">
                                <div class="space-y-6">
                                    <h3 class="text-[10px] font-black text-gray-700 uppercase tracking-widest italic">Jurnal Activitate</h3>
                                    <div class="space-y-3 max-h-[300px] overflow-y-auto pr-2 custom-scrollbar">
                                        ${data.activity.length === 0 ? '<p class="text-gray-800 italic text-xs">Nicio activitate detectată.</p>' : data.activity.map(a => `
                                            <div class="p-3 bg-white/[0.02] border border-white/5 rounded-xl flex justify-between items-center transition-all hover:bg-white/5">
                                                <span class="text-[10px] font-bold text-gray-400 capitalize">${a.activity}</span>
                                                <span class="text-[8px] text-gray-700 font-mono">${a.created_at.split(' ')[1]}</span>
                                            </div>
                                        `).join('')}
                                    </div>
                                </div>
                                <div class="space-y-6">
                                    <h3 class="text-[10px] font-black text-gray-700 uppercase tracking-widest italic">Istoric Achiziții</h3>
                                    <div class="space-y-3 max-h-[300px] overflow-y-auto pr-2 custom-scrollbar">
                                        ${data.sales.length === 0 ? '<p class="text-gray-800 italic text-xs">Nicio achiziție efectuată.</p>' : data.sales.map(s => {
                                            const statusColor = s.status === 'paid' || s.status === 'completed' ? 'text-green-500' : (s.status === 'pending' ? 'text-yellow-500' : 'text-red-500');
                                            return `
                                            <div class="p-4 bg-white/[0.02] border border-white/5 rounded-2xl">
                                                <div class="flex justify-between items-center mb-2">
                                                    <span class="text-[11px] font-black uppercase text-white">${s.item_name}</span>
                                                    <span class="text-[9px] font-black ${statusColor} uppercase">${s.status}</span>
                                                </div>
                                                <div class="flex justify-between text-[8px] font-bold text-gray-800">
                                                    <span>${s.id}</span>
                                                    <span>${s.created_at}</span>
                                                </div>
                                            </div>
                                        `}).join('')}
                                    </div>
                                </div>
                            </div>
                        </div>
                    `
                });
            } catch (e) {
                Swal.fire({ icon: 'error', title: 'Sincronizare Eșuată', text: 'Nu am putut prelua datele.', background: '#0d0d12', color: '#fff' });
            }
        }

        async function abortUser(tgId) {
            const { isConfirmed } = await Swal.fire({
                title: 'RESETARE FLOW?',
                text: "Vrei să închizi toate sesiunile active și protocoalele de achiziție pentru acest utilizator?",
                icon: 'warning',
                showCancelButton: true,
                background: '#0d0d12', color: '#fff',
                confirmButtonColor: '#ef4444',
                confirmButtonText: 'RESETEAZĂ'
            });
            if(isConfirmed) {
                await fetch(`/api/users/${tgId}/reset`, { method: 'POST' });
                Swal.fire({ title: 'FLOW RESETAT', icon: 'success', background: '#0d0d12', color: '#fff' });
                loadUsers();
                loadOps();
            }
        }

        function getActionStyle(text) {
            const t = text.toUpperCase();
            if(t.includes('PAID') || t.includes('DELIVERED')) return 'text-green-400 bg-green-500/10 border-green-500/30';
            if(t.includes('CANCEL')) return 'text-red-400 bg-red-500/10 border-red-500/30';
            if(t.includes('NEW_USER') || t.includes('START')) return 'text-purple-400 bg-purple-500/10 border-purple-500/30';
            if(t.includes('CHECKOUT') || t.includes('STARTED') || t.includes('PURCHASE')) return 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30';
            if(t.includes('VIEWING') || t.includes('CATEGORIES') || t.includes('ITEM')) return 'text-blue-300 bg-blue-500/5 border-blue-500/20';
            return 'text-gray-400 bg-white/5 border-white/10';
        }

        function translateActivity(text) {
            const t = text.toUpperCase();
            if (t.includes('START')) return 'A pornit botul';
            if (t.includes('CATEGORIES')) return 'Se uită la categorii';
            if (t.includes('ITEM')) return 'Vede un produs';
            if (t.includes('PROFILE')) return 'Își verifică profilul';
            if (t.includes('HELP')) return 'Cere ajutor';
            if (t.includes('PURCHASE')) return 'Inițiază achiziție';
            if (t.includes('CANCEL')) return 'A anulat comanda';
            if (t.includes('PAID')) return 'A plătit comanda';
            if (t.includes('SUPPORT')) return 'Vorbeste la suport';
            return text;
        }

        async function loadOps() {
             try {
                const [actRes, statRes] = await Promise.all([
                    fetch('/api/activity'),
                    fetch('/api/stats')
                ]);
                
                if (actRes.status === 403) { window.location.reload(); return; }
                const actData = await actRes.json();
                const statData = await statRes.json();

                // Update Dash Stats with CORRECT IDs & Keys
                document.getElementById('stat-revenue').innerText = statData.revenue;
                document.getElementById('stat-sales').innerText = statData.sales_count;
                document.getElementById('stat-pending').innerText = statData.pending_count;
                document.getElementById('stat-online').innerText = statData.online_count;
                
                const ops = document.getElementById('recent-ops');
                if(!actData.activity || actData.activity.length === 0) {
                     ops.innerHTML = '<div class="text-gray-700 italic text-sm">Se așteaptă pachete de date live...</div>';
                     return;
                }
                
                // Prevent DOM obliteration if no new events arrived
                const feedHash = actData.activity[0] ? actData.activity[0].telegram_id + actData.activity[0].last_activity_at : null;
                if (window.lastLogId === feedHash) return;
                window.lastLogId = feedHash;
                
                ops.innerHTML = actData.activity.map(a => {
                    const style = getActionStyle(a.last_activity);
                    const pfp = a.profile_photo ? '/' + a.profile_photo : 'https://api.dicebear.com/7.x/bottts/svg?seed=' + a.telegram_id;
                    const time = a.last_activity_at ? a.last_activity_at.split(' ')[1] : '--:--';
                    return `
                    <div class="flex flex-col bg-white/[0.02] border border-white/[0.04] rounded-2xl overflow-hidden hover:border-blue-500/20 transition-all shadow-lg group relative">
                        <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-600/50 to-transparent opacity-50 group-hover:opacity-100 transition-opacity"></div>
                        <div class="flex flex-col p-4 md:p-5 cursor-pointer h-full" onclick="toggleDetails(${a.telegram_id}, ${a.telegram_id})">
                             <div class="flex justify-between items-start mb-4">
                                 <div class="flex flex-col">
                                     <span class="text-sm font-black text-white group-hover:text-blue-400 transition-colors w-full truncate">@${a.username || 'ANONIM'}</span>
                                     <span class="text-[9px] text-gray-700 font-mono italic tracking-widest mt-0.5">${time}</span>
                                 </div>
                                 <div class="relative flex-shrink-0">
                                     <img src="${pfp}" class="w-12 h-12 rounded-xl object-cover border border-white/10 shadow-2xl group-hover:scale-110 group-hover:rotate-3 transition-transform">
                                     <div class="absolute -bottom-1 -right-1 w-3.5 h-3.5 bg-green-500 border-2 border-[#050508] rounded-full animate-pulse"></div>
                                 </div>
                             </div>
                             
                             <div class="mt-auto flex justify-between items-end">
                                  <div class="${style} px-3 py-1.5 rounded-xl text-[9px] font-black uppercase tracking-tighter border shadow-sm leading-tight flex-1">
                                      ${translateActivity(a.last_activity)}
                                  </div>
                                  <div class="ml-4 p-2 bg-white/5 rounded-xl group-hover:bg-blue-600/10 transition-colors">
                                      <i class="fas fa-chevron-down text-[10px] text-gray-500 group-hover:text-blue-500 transition-transform transform" id="chevron-${a.telegram_id}"></i>
                                  </div>
                              </div>
                        </div>
                        
                        <div id="details-${a.telegram_id}" class="hidden bg-black/60 border-t border-white/[0.05] p-5">
                            <div class="flex justify-between items-center mb-4">
                                <h4 class="text-[10px] font-black text-blue-500 uppercase tracking-widest italic flex items-center gap-2"><i class="fas fa-route"></i> Istoric</h4>
                                <button onclick="event.stopPropagation(); showUserVault(${a.telegram_id})" class="text-[8px] font-black bg-white/10 text-white hover:bg-white hover:text-black px-3 py-1.5 rounded-full uppercase tracking-widest transition-all">Deschide Seif</button>
                            </div>
                            <div class="space-y-2 max-h-[160px] overflow-y-auto pr-2 custom-scrollbar" id="history-${a.telegram_id}">
                                <div class="text-[10px] text-gray-800 animate-pulse italic">Interogare Matrix...</div>
                            </div>
                        </div>
                    </div>
                `;
                }).join('');
             } catch(e) { console.error("Dash Sync Fail", e); }
        }

        function updateClock() {
            const now = new Date();
            document.getElementById('live-clock').innerText = now.toLocaleTimeString('en-GB');
        }
        setInterval(updateClock, 1000);
        updateClock();

        async function toggleDetails(logId, tgId) {
            const el = document.getElementById('details-' + logId);
            const chev = document.getElementById('chevron-' + logId);
            if(el.classList.contains('hidden')) {
                el.classList.remove('hidden');
                if (chev) chev.style.transform = 'rotate(180deg)';
                // Fetch history
                const res = await fetch('/api/activity-history/' + tgId);
                const data = await res.json();
                const histDiv = document.getElementById('history-' + logId);
                if (!data.history || data.history.length === 0) {
                    histDiv.innerHTML = '<div class="text-gray-800 italic text-[10px]">Nicio activitate istorică găsită.</div>';
                } else {
                    histDiv.innerHTML = data.history.map(h => {
                        const style = getActionStyle(h.activity);
                        return `
                        <div class="flex justify-between items-center py-2 border-b border-white/5 last:border-0 group/hist">
                            <span class="text-[10px] text-gray-400 group-hover/hist:text-white transition-colors">${translateActivity(h.activity)}</span>
                            <span class="text-[9px] text-gray-800 font-mono">${h.created_at.split(' ')[1]}</span>
                        </div>
                    `}).join('');
                }
            } else {
                el.classList.add('hidden');
                if (chev) chev.style.transform = 'rotate(0deg)';
            }
        }
        setInterval(loadOps, 2000); // Live Stream Heartbeat (2s)
        loadOps();

        async function createCategory() {
            const { value: name } = await Swal.fire({ 
                title: 'GENERATE NEW POOL', 
                input: 'text', 
                inputPlaceholder: 'Enter Emoji or Name',
                background: '#111', color: '#fff' 
            });
            if (name) { 
                const form = new FormData(); form.append('name', name);
                await fetch('/api/categories', { method: 'POST', body: form });
                loadStore();
            }
        }

        async function createItem() {
            const res = await fetch('/api/inventory');
            const data = await res.json();
            const { value: formValues } = await Swal.fire({
                title: 'INITIALIZE ASSET NODE',
                html: `<select id="swal-cat" class="swal2-input bg-zinc-900 border-none rounded-xl">${data.categories.map(c => `<option value="${c.id}">${c.name}</option>`).join('')}</select>` +
                      '<input id="swal-name" class="swal2-input border-none rounded-xl" placeholder="Display Name (e.g. ❄️ 10g)">' +
                      '<input id="swal-desc" class="swal2-input border-none rounded-xl" placeholder="Brief Protocol Description">' +
                      '<input id="swal-price" type="number" class="swal2-input border-none rounded-xl" placeholder="Liquidity Value (RON)">',
                focusConfirm: false,
                background: '#0d0d12', color: '#fff',
                customClass: { confirmButton: 'bg-blue-600 rounded-xl px-10 py-3' },
                preConfirm: () => [
                    document.getElementById('swal-cat').value,
                    document.getElementById('swal-name').value,
                    document.getElementById('swal-desc').value,
                    document.getElementById('swal-price').value
                ]
            });
            if (formValues) {
                const form = new FormData();
                form.append('category_id', formValues[0]);
                form.append('name', formValues[1]);
                form.append('description', formValues[2]);
                form.append('price_ron', formValues[3]);
                await fetch('/api/items', { method: 'POST', body: form });
                loadStore();
            }
        }
    </script>
</body>
</html>
"""

@app.get("/api/inventory")
async def get_inventory(request: Request):
    if not is_authenticated(request): return JSONResponse(status_code=403, content={"error": "Unauthorized"})
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cats = [dict(r) for r in await (await db.execute("SELECT * FROM categories")).fetchall()]
        # Explicitly fetching * which now includes is_primary
        items = [dict(r) for r in await (await db.execute("SELECT * FROM items")).fetchall()]
        stock = [dict(r) for r in await (await db.execute("SELECT * FROM item_images WHERE is_sold = 0")).fetchall()]
    for item in items:
        item["stock"] = [s for s in stock if s["item_id"] == item["id"]]
        item["stock_count"] = len(item["stock"])
    return {"categories": cats, "items": items}

@app.post("/api/categories")
async def add_category(request: Request, name: str = Form(...)):
    if not is_authenticated(request): return JSONResponse(status_code=403, content={"error": "Unauthorized"})
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        await db.commit()
    return {"status": "ok"}

@app.post("/api/items")
async def add_item(request: Request, category_id: int = Form(...), name: str = Form(...), description: str = Form(...), price_ron: float = Form(...)):
    if not is_authenticated(request): return JSONResponse(status_code=403, content={"error": "Unauthorized"})
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("INSERT INTO items (category_id, name, description, price_ron, price_ltc) VALUES (?, ?, ?, ?, ?)", 
                         (category_id, name, description, price_ron, price_ron / 300.0))
        await db.commit()
    return {"status": "ok"}

@app.post("/api/stock")
async def add_stock_api(request: Request, item_id: int = Form(...), content: str = Form(None), media_type: str = Form("photo"), caption: str = Form(None), file: UploadFile = File(None)):
    if not is_authenticated(request): return JSONResponse(status_code=403, content={"error": "Unauthorized"})
    if file and file.filename:
        fname = f"stock_{item_id}_{int(time.time())}_{file.filename}"
        fpath = os.path.join("assets", fname)
        with open(fpath, "wb") as f: f.write(await file.read())
        content = fpath
        ext = file.filename.split('.')[-1].lower()
        if ext in ['mp4', 'mov', 'avi']: media_type = 'video'
        elif ext in ['gif']: media_type = 'animation'
        else: media_type = 'photo'
    
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("INSERT INTO item_images (item_id, image_url, media_type, caption) VALUES (?, ?, ?, ?)", 
                         (item_id, content, media_type, caption))
        await db.commit()
    return {"status": "ok"}

@app.delete("/api/items/{id}")
async def delete_item_api(request: Request, id: int):
    if not is_authenticated(request): return JSONResponse(status_code=403, content={"error": "Unauthorized"})
    async with aiosqlite.connect(settings.DB_PATH) as db:
        it = await (await db.execute("SELECT is_primary FROM items WHERE id = ?", (id,))).fetchone()
        if it and it[0]:
            return JSONResponse(status_code=400, content={"error": "Cannot delete primary store items"})
        await db.execute("DELETE FROM items WHERE id = ?", (id,))
        await db.commit()
    return {"status": "ok"}

@app.delete("/api/stock/{id}")
async def delete_stock_api(request: Request, id: int):
    if not is_authenticated(request): return JSONResponse(status_code=403, content={"error": "Unauthorized"})
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("DELETE FROM item_images WHERE id = ?", (id,))
        await db.commit()
    return {"status": "ok"}

@app.get("/api/media/proxy/{file_id:path}")
async def proxy_media(request: Request, file_id: str):
    if not is_authenticated(request): return Response(status_code=403)
    bot = getattr(app.state, "bot", None)
    if not bot: return Response(content=file_id.encode(), media_type="text/plain")
    try:
        if len(file_id) < 15 or file_id.startswith("http") or "/" in file_id: 
            return Response(content=file_id.encode(), media_type="text/plain")
        f = await bot.get_file(file_id)
        d = io.BytesIO()
        await bot.download_file(f.file_path, d)
        return Response(content=d.getvalue(), media_type="image/jpeg")
    except: return Response(content=file_id.encode(), media_type="text/plain")

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>SECURE ACCESS | MOGOSU</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>body {{ background: #060609; color: #fff; display: flex; align-items: center; justify-content: center; height: 100vh; font-family: sans-serif; overflow: hidden; }}</style>
    </head>
    <body class="p-6">
        <div class="w-full max-w-sm bg-white/5 border border-white/10 p-8 rounded-3xl text-center">
            <div class="w-16 h-16 bg-blue-600 rounded-full flex items-center justify-center mx-auto mb-6 shadow-2xl shadow-blue-500/20">
                <i class="fas fa-lock text-white text-xl"></i>
            </div>
            <h1 class="text-2xl font-black italic tracking-tighter mb-2">MOGOSU <span class="text-blue-500">DECODER</span></h1>
            <p class="text-[10px] text-gray-600 font-bold uppercase tracking-widest mb-8 text-center">Enter Access PIN to bridge connection</p>
            <form action="/login" method="post" class="space-y-4">
                <input type="password" name="pin" placeholder="Enter PIN" class="w-full bg-black border border-white/10 rounded-xl px-4 py-3 text-center text-xl font-bold font-mono focus:border-blue-500 outline-none">
                <button type="submit" class="w-full bg-blue-600 py-3 rounded-xl font-black uppercase tracking-widest text-xs hover:bg-blue-500 transition-colors">Authorize Node</button>
            </form>
        </div>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/js/all.min.js"></script>
    </body>
    </html>
    """

@app.post("/login")
async def process_login(response: Response, pin: str = Form(...)):
    if pin == DASHBOARD_PIN:
        response = Response(status_code=303, headers={ "Location": "/" })
        response.set_cookie(key="admin_session", value=pin, max_age=86400 * 7, httponly=True)
        return response
    return Response(status_code=303, headers={ "Location": "/login?error=1" })

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if not is_authenticated(request): return RedirectResponse(url="/login", status_code=303)
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        user_count = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        row = await (await db.execute("SELECT COUNT(*), SUM(amount_paid) FROM sales WHERE status IN ('paid', 'completed')")).fetchone()
    return Template(TEMPLATES_HTML).render(user_count=user_count, sales_count=row[0], revenue=round(row[1] or 0, 4))

@app.get("/api/users")
async def get_users(request: Request):
    if not is_authenticated(request): return JSONResponse(status_code=403, content={"error": "Unauthorized"})
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        users = [dict(r) for r in await (await db.execute("SELECT * FROM users ORDER BY joined_at DESC LIMIT 50")).fetchall()]
    return {"users": users}

@app.get("/api/stats")
async def api_stats(request: Request):
    if not is_authenticated(request): return JSONResponse(status_code=403, content={"error": "Unauthorized"})
    from datetime import datetime, timedelta
    fifteen_mins_ago = (datetime.now() - timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S')
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        sales = await (await db.execute("""
            SELECT COUNT(*) as count, SUM(i.price_ron) as revenue 
            FROM sales s JOIN items i ON s.item_id = i.id
            WHERE s.status IN ('paid', 'completed')
        """)).fetchone()
        pending = await (await db.execute("SELECT COUNT(*) as count FROM sales WHERE status IN ('pending', 'confirming')")).fetchone()
        online = await (await db.execute("SELECT COUNT(*) as count FROM users WHERE last_activity_at > ?", (fifteen_mins_ago,))).fetchone()
        stock = await (await db.execute("SELECT COUNT(*) FROM item_images WHERE is_sold = 0")).fetchone()
        addresses = await (await db.execute("SELECT COUNT(*) FROM addresses")).fetchone()

    return {
        "revenue": f"{sales['revenue'] or 0:.0f} RON",
        "sales_count": sales['count'],
        "pending_count": pending['count'],
        "online_count": online['count'],
        "stock_count": stock[0],
        "address_count": addresses[0]
    }

@app.get("/api/activity")
async def get_activity(request: Request):
    if not is_authenticated(request): return JSONResponse(status_code=403, content={"error": "Unauthorized"})
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        act = [dict(r) for r in await (await db.execute("""
            SELECT telegram_id, username, last_activity, last_activity_at, profile_photo 
            FROM users 
            WHERE last_activity IS NOT NULL 
            ORDER BY last_activity_at DESC 
            LIMIT 50
        """)).fetchall()]
    return {"activity": act}

@app.get("/api/activity-history/{tg_id}")
async def get_activity_history(request: Request, tg_id: int):
    if not is_authenticated(request): return JSONResponse(status_code=403, content={"error": "Unauthorized"})
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        h = [dict(r) for r in await (await db.execute("""
            SELECT activity, created_at FROM user_activity_logs 
            WHERE telegram_id = ? ORDER BY id DESC LIMIT 50
        """, (tg_id,))).fetchall()]
    return {"history": h}

@app.get("/api/addresses")
async def get_addresses(request: Request):
    if not is_authenticated(request): return JSONResponse(status_code=403, content={"error": "Unauthorized"})
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        addr = [dict(r) for r in await (await db.execute("SELECT * FROM addresses")).fetchall()]
    return {"addresses": addr}

@app.post("/api/addresses")
async def post_address(request: Request, address: str = Form(...)):
    if not is_authenticated(request): return JSONResponse(status_code=403, content={"error": "Unauthorized"})
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("INSERT INTO addresses (crypto_address) VALUES (?)", (address,))
        await db.commit()
    return {"status": "ok"}

@app.put("/api/addresses/{id}")
async def put_address(request: Request, id: int, address: str = Form(...)):
    if not is_authenticated(request): return JSONResponse(status_code=403, content={"error": "Unauthorized"})
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("UPDATE addresses SET crypto_address = ? WHERE id = ?", (address, id))
        await db.commit()
    return {"status": "ok"}

@app.delete("/api/addresses/{id}")
async def remove_address(request: Request, id: int):
    if not is_authenticated(request): return JSONResponse(status_code=403, content={"error": "Unauthorized"})
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("DELETE FROM addresses WHERE id = ?", (id,))
        await db.commit()

@app.post("/api/users/{tg_id}/reset")
async def reset_user_flow(request: Request, tg_id: int):
    if not is_authenticated(request): return JSONResponse(status_code=403, content={"error": "Unauthorized"})
    async with aiosqlite.connect(settings.DB_PATH) as db:
        # Cancel all pending sales for this user
        await db.execute("UPDATE sales SET status = 'cancelled' WHERE user_id = (SELECT id FROM users WHERE telegram_id = ?) AND status = 'pending'", (tg_id,))
        # Log the intervention
        await db.execute("INSERT INTO user_activity_logs (telegram_id, activity) VALUES (?, ?)", (tg_id, "ADMIN_RESET_FLOW"))
        await db.commit()
    return {"status": "ok"}

@app.get("/api/user-profile/{tg_id}")
async def get_user_profile(request: Request, tg_id: int):
    if not is_authenticated(request): return JSONResponse(status_code=403, content={"error": "Unauthorized"})
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        user = await (await db.execute("SELECT * FROM users WHERE telegram_id = ?", (tg_id,))).fetchone()
        if not user: return JSONResponse(status_code=404, content={"error": "Not Found"})
        
        activity = [dict(r) for r in await (await db.execute("SELECT activity, created_at FROM user_activity_logs WHERE telegram_id = ? ORDER BY created_at DESC LIMIT 50", (tg_id,))).fetchall()]
        sales = [dict(r) for r in await (await db.execute("""
            SELECT s.*, i.name as item_name 
            FROM sales s JOIN items i ON s.item_id = i.id 
            WHERE s.user_id = ? ORDER BY s.created_at DESC
        """, (user['id'],))).fetchall()]
        
    return {
        "user": dict(user),
        "activity": activity,
        "sales": sales
    }
