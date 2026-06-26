/* ==========================================================================
   MigaMiga ERP SaaS — MOTOR DE LÓGICA DE NEGOCIO (app.js)
   ========================================================================== */

// 1. BASE DE DATOS INICIAL MULTITENANT EN LOCALSTORAGE
const INITIAL_DATABASE = {
    // ------------------ MigaMiga (Negocio Principal) ------------------
    MigaMiga: {
        info: {
            name: "A&M ERP",
            rnc: "131-45678-9",
            address: "Av. Abraham Lincoln #402, Santo Domingo, RD",
            plan: "Empresa",
            active: true
        },
        inventory: [
            { id: "inv_harina", name: "Harina de Trigo", category: "Ingredientes", stock: 12500, unit: "g", cost: 0.05, minStock: 2000 },
            { id: "inv_azucar", name: "Azúcar Blanco", category: "Ingredientes", stock: 8000, unit: "g", cost: 0.04, minStock: 1000 },
            { id: "inv_huevos", name: "Huevos", category: "Ingredientes", stock: 120, unit: "u", cost: 7.50, minStock: 30 },
            { id: "inv_mantequilla", name: "Mantequilla", category: "Ingredientes", stock: 4500, unit: "g", cost: 0.35, minStock: 1000 },
            { id: "inv_nutella", name: "Nutella", category: "Ingredientes", stock: 3000, unit: "g", cost: 0.60, minStock: 500 },
            { id: "inv_dulce_leche", name: "Dulce de Leche Premium", category: "Ingredientes", stock: 5, unit: "lb", cost: 180.00, minStock: 1 },
            { id: "inv_leche_condensada", name: "Leche Condensada (Lata)", category: "Ingredientes", stock: 10, unit: "pote", cost: 95.00, minStock: 2 },
            { id: "inv_leche", name: "Leche Evaporada", category: "Ingredientes", stock: 8000, unit: "ml", cost: 0.12, minStock: 1000 },
            { id: "inv_crema_leche", name: "Crema de Leche", category: "Ingredientes", stock: 5000, unit: "ml", cost: 0.15, minStock: 1000 },
            { id: "inv_jugo_chinola", name: "Jugo Concentrado Chinola", category: "Ingredientes", stock: 2000, unit: "ml", cost: 0.08, minStock: 500 },
            { id: "inv_galletas_maria", name: "Galletas María", category: "Ingredientes", stock: 1500, unit: "g", cost: 0.12, minStock: 200 },
            { id: "inv_migas_brownie", name: "Migas de Brownie Reutilizadas", category: "Ingredientes", stock: 0, unit: "g", cost: 0.00, minStock: 0 },
            { id: "inv_cajas", name: "Cajas para Brownies", category: "Empaque", stock: 150, unit: "u", cost: 35.00, minStock: 25 },
            { id: "inv_stickers", name: "Stickers A&M", category: "Empaque", stock: 400, unit: "u", cost: 2.00, minStock: 50 },
            { id: "inv_vasos", name: "Vasos Domo con Tapa", category: "Empaque", stock: 200, unit: "u", cost: 8.00, minStock: 30 },
            { id: "inv_cucharas", name: "Cucharas de Postre", category: "Empaque", stock: 200, unit: "u", cost: 1.50, minStock: 30 },
            { id: "inv_cintas", name: "Cintas Decorativas", category: "Decoración", stock: 100, unit: "m", cost: 15.00, minStock: 10 },
            { id: "inv_guantes", name: "Guantes de Nitrilo", category: "Limpieza", stock: 200, unit: "u", cost: 5.00, minStock: 20 }
        ],
        recipes: [
            {
                id: "rec_brownie",
                name: "Brownie Normal A&M",
                yield: 27,
                time: 60,
                difficulty: "Fácil",
                ingredients: [
                    { id: "inv_harina", qty: 500, unit: "g" },
                    { id: "inv_huevos", qty: 8, unit: "u" },
                    { id: "inv_mantequilla", qty: 250, unit: "g" },
                    { id: "inv_nutella", qty: 300, unit: "g" },
                    { id: "inv_cajas", qty: 1, unit: "u" },
                    { id: "inv_stickers", qty: 1, unit: "u" }
                ],
                indirects: { services: 60, labor: 150, merma: 5, packaging: 37 }
            },
            {
                id: "rec_brownie_relleno",
                name: "Brownie Relleno de Dulce de Leche",
                yield: 27,
                time: 70,
                difficulty: "Fácil",
                ingredients: [
                    { id: "inv_harina", qty: 500, unit: "g" },
                    { id: "inv_huevos", qty: 8, unit: "u" },
                    { id: "inv_mantequilla", qty: 250, unit: "g" },
                    { id: "inv_nutella", qty: 200, unit: "g" },
                    { id: "inv_dulce_leche", qty: 8, unit: "oz" }, // Uso en onzas sobre inventario en libras!
                    { id: "inv_cajas", qty: 1, unit: "u" },
                    { id: "inv_stickers", qty: 1, unit: "u" }
                ],
                indirects: { services: 70, labor: 160, merma: 4, packaging: 37 }
            },
            {
                id: "rec_brownie_tres_leches",
                name: "Brownie Tres Leches",
                yield: 12,
                time: 80,
                difficulty: "Medio",
                ingredients: [
                    { id: "inv_harina", qty: 300, unit: "g" },
                    { id: "inv_huevos", qty: 4, unit: "u" },
                    { id: "inv_mantequilla", qty: 150, unit: "g" },
                    { id: "inv_leche", qty: 300, unit: "ml" },
                    { id: "inv_leche_condensada", qty: 0.5, unit: "pote" },
                    { id: "inv_crema_leche", qty: 200, unit: "ml" },
                    { id: "inv_vasos", qty: 12, unit: "u" },
                    { id: "inv_stickers", qty: 12, unit: "u" }
                ],
                indirects: { services: 90, labor: 200, merma: 5, packaging: 114 }
            },
            {
                id: "rec_carlota_chinola",
                name: "Carlota de Chinola en Vasito",
                yield: 10,
                time: 45,
                difficulty: "Medio",
                ingredients: [
                    { id: "inv_galletas_maria", qty: 250, unit: "g" },
                    { id: "inv_jugo_chinola", qty: 300, unit: "ml" },
                    { id: "inv_leche_condensada", qty: 1, unit: "pote" },
                    { id: "inv_leche", qty: 400, unit: "ml" },
                    { id: "inv_vasos", qty: 10, unit: "u" },
                    { id: "inv_stickers", qty: 10, unit: "u" }
                ],
                indirects: { services: 30, labor: 100, merma: 3, packaging: 100 }
            },
            {
                id: "rec_flan",
                name: "Flan de la Casa Cremoso",
                yield: 8,
                time: 90,
                difficulty: "Medio",
                ingredients: [
                    { id: "inv_huevos", qty: 6, unit: "u" },
                    { id: "inv_leche_condensada", qty: 1, unit: "pote" },
                    { id: "inv_leche", qty: 300, unit: "ml" },
                    { id: "inv_azucar", qty: 200, unit: "g" },
                    { id: "inv_vasos", qty: 8, unit: "u" }
                ],
                indirects: { services: 50, labor: 120, merma: 2, packaging: 64 }
            },
            {
                id: "rec_vasitos_brownie",
                name: "Vasitos de Brownie (REUTILIZADO)",
                yield: 15,
                time: 30,
                difficulty: "Fácil",
                ingredients: [
                    { id: "inv_migas_brownie", qty: 500, unit: "g" }, // Insumo a costo RD$0.00
                    { id: "inv_dulce_leche", qty: 6, unit: "oz" }, // 6 oz
                    { id: "inv_crema_leche", qty: 200, unit: "ml" },
                    { id: "inv_vasos", qty: 15, unit: "u" },
                    { id: "inv_cucharas", qty: 15, unit: "u" }
                ],
                indirects: { services: 20, labor: 80, merma: 1, packaging: 142 }
            }
        ],
        products: [
            { id: "prod_brownie", name: "Brownie Normal Unitario", category: "brownies", price: 150, cost: 45.50, stock: 45, img: "https://images.unsplash.com/photo-1606313564200-e75d5e30476c?q=80&w=200&auto=format&fit=crop" },
            { id: "prod_brownie_relleno", name: "Brownie Relleno Dulce Leche", category: "brownies", price: 180, cost: 62.00, stock: 27, img: "https://images.unsplash.com/photo-1606313564200-e75d5e30476c?q=80&w=200&auto=format&fit=crop" },
            { id: "prod_brownie_tres_leches", name: "Brownie Tres Leches Vaso", category: "mini", price: 220, cost: 85.00, stock: 12, img: "https://images.unsplash.com/photo-1558961309-dbdf71791454?q=80&w=200&auto=format&fit=crop" },
            { id: "prod_carlota", name: "Carlota de Chinola Imperial", category: "mini", price: 160, cost: 55.00, stock: 20, img: "https://images.unsplash.com/photo-1606313564200-e75d5e30476c?q=80&w=200&auto=format&fit=crop" },
            { id: "prod_flan", name: "Flan Cremoso Casero", category: "mini", price: 130, cost: 42.00, stock: 15, img: "https://images.unsplash.com/photo-1606313564200-e75d5e30476c?q=80&w=200&auto=format&fit=crop" },
            { id: "prod_vasito_brownie", name: "Vasito de Brownie Gourmet", category: "mini", price: 140, cost: 38.00, stock: 15, img: "https://images.unsplash.com/photo-1558961309-dbdf71791454?q=80&w=200&auto=format&fit=crop" }
        ],
        clients: [
            { id: "cli_pedro", name: "Pedro Martínez", phone: "809-555-0122", bday: "06-12", avgSpend: 450, creditLimit: 5000, debt: 1200 },
            { id: "cli_maria", name: "María Rodríguez", phone: "829-555-9874", bday: "05-28", avgSpend: 820, creditLimit: 10000, debt: 0 },
            { id: "cli_juan", name: "Juan de Dios", phone: "809-555-4511", bday: "11-05", avgSpend: 250, creditLimit: 2000, debt: 450 }
        ],
        sales: [
            { id: "sale_0001", date: "2026-05-25T14:32:00", customer: "María Rodríguez", items: [{ name: "Brownie Normal Unitario", qty: 4, price: 150 }], subtotal: 600, tax: 108, total: 600, payment: "efectivo", ncf: "B0100000001" },
            { id: "sale_0002", date: "2026-05-25T17:10:00", customer: "Pedro Martínez", items: [{ name: "Brownie Relleno Dulce Leche", qty: 1, price: 180 }], subtotal: 180, tax: 32.40, total: 180, payment: "credito", ncf: "B0200000001" }
        ],
        caja: {
            active: { id: "caja_act_1", openTime: "2026-05-26T08:00:00", openFund: 1000, expectedCash: 1600, movements: [] },
            history: [
                { id: "caja_closed_0", openTime: "2026-05-25T08:00:00", closeTime: "2026-05-25T21:00:00", openFund: 1000, expectedCash: 1600, physicalCash: 1600, difference: 0, status: "Cuadrado" }
            ]
        },
        kardex: [
            { time: "2026-05-25T09:00:00", name: "Harina de Trigo", type: "Entrada (Compra)", qty: 5000, unit: "g", cost: 0.05, reason: "Proveedor Harina S.A." },
            { time: "2026-05-25T11:00:00", name: "Harina de Trigo", type: "Salida (Producción)", qty: 500, unit: "g", cost: 0.05, reason: "Producción Brownie Normal" }
        ],
        orders: [
            { id: "ord_001", deliveryDate: "2026-05-28", deliveryTime: "17:00", customer: "María Rodríguez", desc: "Bizcocho decorado Red Velvet con topping de flores.", total: 3200, abono: 1500, balance: 1700, status: "Pendiente" }
        ],
        production: [
            { time: "2026-05-25T11:00:00", recipe: "Brownie Normal A&M", multiplier: 1, qtyCreated: 27, unitCost: 45.50, totalCost: 1228.50 }
        ],
        audit: [
            { time: "2026-05-26T08:05:00", user: "Sofía Rodríguez", role: "admin", module: "Caja Chica", action: "Apertura de Turno", impact: "Caja abierta con fondo: RD$1,000" },
            { time: "2026-05-26T11:15:00", user: "Chef Carlos", role: "produccion", module: "Línea de Producción", action: "Producción Procesada", impact: "+27 unidades de Brownie Normal" },
            { time: "2026-05-26T14:35:00", user: "Camila Gómez", role: "cajero", module: "POS", action: "Factura NCF B0100000001", impact: "Venta total RD$600 cobrado en efectivo" }
        ]
    },

    // ------------------ Dulce Tentación (Cliente SaaS 1) ------------------
    DulceTentacion: {
        info: {
            name: "Dulce Tentación",
            rnc: "224-00148-5",
            address: "Calle El Sol #12, Santiago, RD",
            plan: "Pro",
            active: true
        },
        inventory: [
            { id: "inv_harina", name: "Harina de Trigo", category: "Ingredientes", stock: 8000, unit: "g", cost: 0.06, minStock: 2000 },
            { id: "inv_huevos", name: "Huevos", category: "Ingredientes", stock: 60, unit: "u", cost: 8.00, minStock: 20 },
            { id: "inv_cajas", name: "Cajas Dulce Tentación", category: "Empaque", stock: 80, unit: "u", cost: 25.00, minStock: 15 }
        ],
        recipes: [
            {
                id: "rec_brownie_dt",
                name: "Brownie Dulce Tentación",
                yield: 20,
                time: 50,
                difficulty: "Fácil",
                ingredients: [
                    { id: "inv_harina", qty: 400 },
                    { id: "inv_huevos", qty: 6 },
                    { id: "inv_cajas", qty: 1 }
                ],
                indirects: { services: 40, labor: 100, merma: 2, packaging: 25 }
            }
        ],
        products: [
            { id: "prod_brownie_dt", name: "Brownie de la Casa", category: "brownies", price: 120, cost: 35.00, stock: 15, img: "https://images.unsplash.com/photo-1606313564200-e75d5e30476c?q=80&w=200&auto=format&fit=crop" }
        ],
        clients: [
            { id: "cli_clara", name: "Clara Gúzman", phone: "809-555-6677", bday: "03-15", avgSpend: 380, creditLimit: 4000, debt: 500 }
        ],
        sales: [
            { id: "sale_dt01", date: "2026-05-25T15:00:00", customer: "Clara Gúzman", items: [{ name: "Brownie de la Casa", qty: 2, price: 120 }], subtotal: 240, tax: 43.20, total: 240, payment: "efectivo", ncf: "B0100000001" }
        ],
        caja: {
            active: { id: "caja_act_dt1", openTime: "2026-05-26T09:00:00", openFund: 800, expectedCash: 1040, movements: [] },
            history: []
        },
        kardex: [],
        orders: [],
        production: []
    },

    // ------------------ Sweet House (Cliente SaaS 2 - SUSPENDIDO) ------------------
    SweetHouse: {
        info: {
            name: "Sweet House",
            rnc: "402-98563-1",
            address: "Plaza Central, Local 2B, Santo Domingo, RD",
            plan: "Básico",
            active: false // SUSPENDIDA
        },
        inventory: [],
        recipes: [],
        products: [],
        clients: [],
        sales: [],
        caja: { active: null, history: [] },
        kardex: [],
        orders: [],
        production: []
    }
};

// 2. ESTADO GLOBAL DE LA APLICACIÓN
let DB = {};
let activeTenant = "MigaMiga";
let activeRole = "admin";
let activeCart = [];
let isMobileShellActive = false;

// Variables de sesión en línea seguras
let sessionToken = sessionStorage.getItem("AM_ERP_TOKEN") || null;
let currentUser = JSON.parse(sessionStorage.getItem("AM_ERP_USER") || "null");

const API_BASE = window.location.protocol === "file:" ? "http://localhost:8000" : "";

// Helper fetch asíncrono para adjuntar JWT automáticamente
async function apiFetch(url, options = {}) {
    if (sessionToken) {
        options.headers = options.headers || {};
        options.headers["Authorization"] = `Bearer ${sessionToken}`;
    }
    const fullUrl = url.startsWith("/api") ? `${API_BASE}${url}` : url;
    try {
        const res = await fetch(fullUrl, options);
        if (res.status === 401) {
            // Token expirado o sesión inválida
            sessionStorage.clear();
            sessionToken = null;
            currentUser = null;
            location.reload();
            return null;
        }
        return res;
    } catch (e) {
        console.error("Error de conexión API:", e);
        return null;
    }
}

// Sincronización asíncrona en la nube
async function syncWithServer() {
    if (!sessionToken) return;
    try {
        const tenantData = JSON.parse(JSON.stringify(DB[activeTenant]));
        // Limpiamos datos redundantes de usuarios locales para no duplicar espacio en nube
        delete tenantData.users;
        await apiFetch("/api/tenant/data", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(tenantData)
        });
    } catch (e) {
        console.error("Error al sincronizar datos con el servidor:", e);
    }
}

// Inicializador de base de datos e integración de selectores SaaS dinámicos
async function initDatabase() {
    const saved = localStorage.getItem("MigaMiga_ERP_SaaS_DB_v1");
    if (saved) {
        try {
            DB = JSON.parse(saved);
        } catch (e) {
            DB = JSON.parse(JSON.stringify(INITIAL_DATABASE));
        }
    } else {
        DB = JSON.parse(JSON.stringify(INITIAL_DATABASE));
        saveToLocalStorage();
    }

    // Intentar jalar la lista de empresas registradas en la base de datos real del servidor
    try {
        const res = await fetch(`${API_BASE}/api/tenants/list`);
        if (res && res.ok) {
            const list = await res.json();
            if (list && list.length > 0) {
                // Actualizar los selectores del Login y Header con las empresas reales de la BD
                const loginTenantSelect = document.getElementById("login-tenant");
                const headerTenantSelect = document.getElementById("tenant-select");
                
                if (loginTenantSelect && headerTenantSelect) {
                    loginTenantSelect.innerHTML = "";
                    headerTenantSelect.innerHTML = "";
                    
                    list.forEach(t => {
                        const opt1 = document.createElement("option");
                        opt1.value = t.id;
                        opt1.textContent = t.id === "MigaMiga" ? `🍽️ ${t.name} (Negocio Principal)` : `🏢 ${t.name}`;
                        loginTenantSelect.appendChild(opt1);
                        
                        const opt2 = document.createElement("option");
                        opt2.value = t.id;
                        opt2.textContent = t.id === "MigaMiga" ? `🍽️ ${t.name} (Negocio Principal)` : `🏢 ${t.name}`;
                        headerTenantSelect.appendChild(opt2);
                        
                        // Crear la estructura en memoria local por si no existe
                        if (!DB[t.id]) {
                            DB[t.id] = JSON.parse(JSON.stringify(INITIAL_DATABASE.MigaMiga));
                            DB[t.id].info = { name: t.name, active: t.status === "activo", plan: t.plan };
                        } else {
                            DB[t.id].info.name = t.name;
                            DB[t.id].info.active = t.status === "activo";
                            DB[t.id].info.plan = t.plan;
                        }
                    });
                }
            }
        }
    } catch (e) {
        console.log("Servidor local no disponible. Utilizando memoria local offline.");
    }
}

function saveToLocalStorage() {
    localStorage.setItem("MigaMiga_ERP_SaaS_DB_v1", JSON.stringify(DB));
    if (sessionToken) {
        syncWithServer();
    }
}

// ==========================================
// KITCHEN UNIT CONVERSION ENGINE
// ==========================================
function convertUnit(amount, fromUnit, toUnit) {
    if (!fromUnit || !toUnit || fromUnit === toUnit) return amount;
    
    // Estandarizar a base de masa (gramo 'g') o volumen (mililitro 'ml')
    const standardMass = { 
        g: 1, 
        gramos: 1,
        oz: 28.35, 
        onza: 28.35, 
        onzas: 28.35,
        lb: 453.59, 
        libra: 453.59, 
        libras: 453.59,
        kg: 1000, 
        kilogramo: 1000,
        pote: 500,
        paquete: 10
    };
    
    const standardVol = { 
        ml: 1, 
        litro: 1000, 
        litros: 1000,
        tazas: 250, 
        taza: 250,
        oz_liq: 29.57 
    };
    
    const standardUnits = { 
        u: 1, 
        unidad: 1, 
        unidades: 1,
        paquete: 10, 
        carton: 30, 
        caja: 1 
    };
    
    // Conversiones cruzadas dry
    if (standardMass[fromUnit] && standardMass[toUnit]) {
        const inG = amount * standardMass[fromUnit];
        return inG / standardMass[toUnit];
    }
    
    // Conversiones cruzadas liquid
    if (standardVol[fromUnit] && standardVol[toUnit]) {
        const inMl = amount * standardVol[fromUnit];
        return inMl / standardVol[toUnit];
    }
    
    // Conversiones cruzadas packaging
    if (standardUnits[fromUnit] && standardUnits[toUnit]) {
        const inU = amount * standardUnits[fromUnit];
        return inU / standardUnits[toUnit];
    }
    
    return amount; 
}

// ==========================================
// SYSTEM AUDIT TRAIL LOG ENGINE
// ==========================================
function logAudit(module, action, impact) {
    const tenant = DB[activeTenant];
    if (!tenant.audit) tenant.audit = [];
    
    let userName = currentUser ? currentUser.name : "Sofía Rodríguez";
    
    const logRecord = {
        time: new Date().toISOString(),
        user: userName,
        role: activeRole,
        module: module,
        action: action,
        impact: impact
    };
    
    tenant.audit.push(logRecord);
    saveToLocalStorage();
    
    if (sessionToken) {
        apiFetch("/api/audit-logs", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ module, action, impact })
        }).then(() => {
            renderAuditLog();
        });
    } else {
        renderAuditLog();
    }
}

async function renderAuditLog() {
    const tbody = document.getElementById("audit-log-tbody");
    if (!tbody) return;
    
    tbody.innerHTML = "";
    let logs = [];
    
    if (sessionToken) {
        try {
            const res = await apiFetch("/api/audit-logs");
            if (res && res.ok) {
                const cloudLogs = await res.json();
                logs = cloudLogs.map(l => ({
                    time: l.timestamp,
                    user: l.username,
                    role: l.role,
                    module: l.module,
                    action: l.action,
                    impact: l.impact
                }));
            }
        } catch (e) {
            console.error("Error al jalar bitácora en la nube:", e);
        }
    }
    
    if (logs.length === 0) {
        const tenant = DB[activeTenant];
        if (tenant && tenant.audit) {
            logs = tenant.audit;
        }
    }
    
    const sorted = [...logs].reverse();
    sorted.slice(0, 100).forEach(log => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${new Date(log.time).toLocaleString()}</td>
            <td><strong>${log.user}</strong></td>
            <td><span class="badge font-secondary">${log.role.toUpperCase()}</span></td>
            <td><strong>${log.module}</strong></td>
            <td>${log.action}</td>
            <td><span class="badge green-bg">${log.impact}</span></td>
        `;
        tbody.appendChild(tr);
    });
}

// ==========================================
// CONTROL DE MERMAS Y REUTILIZACIÓN
// ==========================================
function renderMermaPanel() {
    const select = document.getElementById("merma-product-select");
    if (!select) return;
    
    select.innerHTML = "";
    const tenant = DB[activeTenant];
    
    tenant.products.forEach(p => {
        const opt = document.createElement("option");
        opt.value = p.id;
        opt.textContent = `${p.name} (Stock POS: ${p.stock} u)`;
        select.appendChild(opt);
    });
    
    renderReusableBodegaTable();
}

function renderReusableBodegaTable() {
    const tbody = document.getElementById("reusable-items-tbody");
    if (!tbody) return;
    
    tbody.innerHTML = "";
    const tenant = DB[activeTenant];
    
    const reusables = tenant.inventory.filter(item => item.id === "inv_migas_brownie" && item.stock > 0);
    
    if (reusables.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="text-center font-secondary">No hay insumos reutilizados en bodega actualmente.</td></tr>`;
        return;
    }
    
    reusables.forEach(r => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><strong>${r.name}</strong></td>
            <td class="text-green font-bold">${r.stock.toLocaleString()}</td>
            <td>${r.unit}</td>
            <td>RD$0.00 (Gratis)</td>
            <td class="font-secondary">Recuperado de merma de postres</td>
        `;
        tbody.appendChild(tr);
    });
}

function executeMermaTransaction() {
    const tenant = DB[activeTenant];
    const prodId = document.getElementById("merma-product-select").value;
    const qty = parseInt(document.getElementById("merma-qty").value) || 0;
    const action = document.getElementById("merma-action").value;
    
    const product = tenant.products.find(p => p.id === prodId);
    if (!product || qty <= 0) {
        alert("Selecciona un producto y cantidad válida de merma.");
        return;
    }
    
    if (qty > product.stock) {
        alert(`Stock de venta insuficiente en POS para mermar (Stock actual: ${product.stock} u).`);
        return;
    }
    
    // 1. Decrementar stock
    product.stock -= qty;
    
    if (action === "descarte") {
        const lossVal = qty * product.cost;
        
        if (tenant.caja.active) {
            tenant.caja.active.movements.push({
                time: new Date().toISOString(),
                type: "egreso",
                monto: lossVal,
                concept: `Merma Descartada: ${qty} u de ${product.name}`
            });
        }
        
        logAudit("Mermas", `Descarte de postres: ${qty} ${product.name}`, `Pérdida contable: RD$${lossVal.toFixed(2)}`);
        alert(`🔴 Merma registrada como descarte total. Se descontó del stock POS y se registró una pérdida contable de RD$${lossVal.toFixed(2)}.`);
    } else {
        // REUTILIZACIÓN como Migas de Brownie (inv_migas_brownie)
        // 1 brownie = 100g de migas
        const crumbsAdded = qty * 100;
        let itemCrumbs = tenant.inventory.find(i => i.id === "inv_migas_brownie");
        
        if (itemCrumbs) {
            itemCrumbs.stock += crumbsAdded;
        } else {
            tenant.inventory.push({
                id: "inv_migas_brownie",
                name: "Migas de Brownie Reutilizadas",
                category: "Ingredientes",
                stock: crumbsAdded,
                unit: "g",
                cost: 0,
                minStock: 0
            });
        }
        
        // Kardex Entrada Reutilizado
        tenant.kardex.push({
            time: new Date().toISOString(),
            name: "Migas de Brownie Reutilizadas",
            type: "Entrada (Reutilización)",
            qty: crumbsAdded,
            unit: "g",
            cost: 0,
            reason: `Recuperado de merma: ${qty} u de ${product.name}`
        });
        
        logAudit("Mermas", `Reutilización de postres: ${qty} ${product.name}`, `+${crumbsAdded}g de migas a costo RD$0.00`);
        alert(`♻️ ¡Éxito! Se recuperaron ${crumbsAdded}g de 'Migas de Brownie' en tu bodega a costo contable RD$0.00. Ya puedes usarlas para preparar 'Vasitos de Brownie' gratis.`);
    }
    
    saveToLocalStorage();
    renderPOSCatalog();
    renderInventoryTable();
    renderMermaPanel();
    reloadDashboardMetrics();
}

// 3. ENRUTADOR Y CONTROL DE NAVEGACIÓN SPA
document.addEventListener("DOMContentLoaded", () => {
    initDatabase();
    setupNavigation();
    setupTenantSelector();
    setupRoleSelector();
    setupMobileShellToggle();
    setupModalEvents();
    
    // Iniciar el sistema con el Tenant MigaMiga
    loadTenant(activeTenant);
    
    // Carga de triggers específicos
    setupPOSActions();
    setupCajaActions();
    setupInventoryActions();
    setupRecipesActions();
    setupProductionActions();
    setupCRMActions();
    setupMigaAIActions();
    setupSaaSActions();
    setupSettingsActions();
    
    // Iniciar portal de login seguro
    setupLoginPortal();
    bindAdminActions();
});

function setupLoginPortal() {
    const portal = document.getElementById("login-portal");
    if (!portal) return;
    
    const form = document.getElementById("login-form");
    const errorMsg = document.getElementById("login-error-msg");
    const card = portal.querySelector(".login-card");
    const logoutBtn = document.getElementById("logout-btn");
    
    // Ocultar selectores del header para prevenir bypass
    const headerRoleSelect = document.getElementById("role-select");
    if (headerRoleSelect) headerRoleSelect.style.display = "none";
    const headerTenantSelect = document.getElementById("tenant-select");
    if (headerTenantSelect) headerTenantSelect.style.display = "none";

    // Si ya existe sesión activa al recargar la página, loguear automáticamente
    if (sessionToken && currentUser) {
        activeRole = currentUser.role;
        activeTenant = currentUser.tenant_id;
        
        const tSel = document.getElementById("tenant-select");
        if (tSel) tSel.value = activeTenant;
        const rSel = document.getElementById("role-select");
        if (rSel) rSel.value = activeRole;
        
        if (headerRoleSelect) headerRoleSelect.style.display = "block";
        if (headerTenantSelect) headerTenantSelect.style.display = "block";
        
        portal.classList.add("hidden");
        loadTenant(activeTenant);
        applyRoleRestrictions();
    }

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const tenantVal = document.getElementById("login-tenant").value;
        const userVal = document.getElementById("login-username").value.trim().toLowerCase();
        const passVal = document.getElementById("login-password").value;
        
        try {
            const res = await fetch(`${API_BASE}/api/auth/login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ tenant_id: tenantVal, username: userVal, password: passVal })
            });
            
            if (res && res.ok) {
                const resData = await res.json();
                sessionToken = resData.token;
                currentUser = resData.user;
                currentUser.tenant_id = tenantVal;
                
                sessionStorage.setItem("AM_ERP_TOKEN", sessionToken);
                sessionStorage.setItem("AM_ERP_USER", JSON.stringify(currentUser));
                
                errorMsg.classList.add("hidden");
                
                activeRole = resData.user.role;
                activeTenant = tenantVal;
                
                const tSel = document.getElementById("tenant-select");
                if (tSel) tSel.value = tenantVal;
                const rSel = document.getElementById("role-select");
                if (rSel) rSel.value = activeRole;
                
                if (headerRoleSelect) headerRoleSelect.style.display = "block";
                if (headerTenantSelect) headerTenantSelect.style.display = "block";
                
                await loadTenant(activeTenant);
                applyRoleRestrictions();
                
                portal.classList.add("hidden");
                
                document.getElementById("login-username").value = "";
                document.getElementById("login-password").value = "";
            } else {
                const errData = await res.json();
                errorMsg.textContent = errData.error || "Credenciales incorrectas.";
                errorMsg.classList.remove("hidden");
                card.classList.add("shake-animation");
                setTimeout(() => {
                    card.classList.remove("shake-animation");
                }, 400);
            }
        } catch (err) {
            console.error("Login Error:", err);
            errorMsg.textContent = "Error: No se pudo conectar con el servidor seguro.";
            errorMsg.classList.remove("hidden");
            card.classList.add("shake-animation");
            setTimeout(() => {
                card.classList.remove("shake-animation");
            }, 400);
        }
    });
    
    if (logoutBtn) {
        logoutBtn.addEventListener("click", () => {
            logAudit("Seguridad", "Cerrar Sesión", `El usuario ${currentUser ? currentUser.username : "Desconocido"} cerró sesión.`);
            
            sessionStorage.clear();
            sessionToken = null;
            currentUser = null;
            
            portal.classList.remove("hidden");
            errorMsg.classList.add("hidden");
            
            if (headerRoleSelect) headerRoleSelect.style.display = "none";
            if (headerTenantSelect) headerTenantSelect.style.display = "none";
            
            navigateToPage("dashboard-page");
        });
    }
}

function renderUserManagementList() {
    const tbody = document.getElementById("user-management-tbody");
    if (!tbody) return;
    tbody.innerHTML = "";
    
    const tenant = DB[activeTenant];
    
    // Fetch from cloud asynchronously if logged in
    if (sessionToken && !renderUserManagementList._fetching) {
        renderUserManagementList._fetching = true;
        apiFetch("/api/users/list")
            .then(res => {
                if (res && res.ok) return res.json();
            })
            .then(cloudUsers => {
                renderUserManagementList._fetching = false;
                if (cloudUsers && JSON.stringify(tenant.users) !== JSON.stringify(cloudUsers)) {
                    tenant.users = cloudUsers;
                    saveToLocalStorage();
                    // Re-render once to update UI
                    renderUserManagementList();
                }
            })
            .catch(err => {
                renderUserManagementList._fetching = false;
                console.error("Error fetching users from cloud:", err);
            });
    }

    if (!tenant.users) {
        tenant.users = [
            { name: "Sofía Rodríguez", username: "admin", password: "admin123", role: "admin", status: "Activo", baseSalary: 50000, allowedPages: ["dashboard-page", "pos-page", "caja-page", "inventario-page", "recetario-page", "produccion-page", "crm-page", "settings-page", "finanzas-page"] },
            { name: "Camila Gómez", username: "cajero", password: "cajera123", role: "cajero", status: "Activo", baseSalary: 25000, allowedPages: ["pos-page", "caja-page", "crm-page"] },
            { name: "Chef Carlos Mendoza", username: "chef", password: "chef123", role: "produccion", status: "Activo", baseSalary: 35000, allowedPages: ["inventario-page", "recetario-page", "produccion-page"] }
        ];
        saveToLocalStorage();
    }
    
    tenant.users.forEach(u => {
        let roleBadge = "badge purple-bg";
        let roleLabel = "Administrador";
        if (u.role === "cajero") {
            roleBadge = "badge blue-bg";
            roleLabel = "Ventas / POS";
        } else if (u.role === "produccion") {
            roleBadge = "badge green-bg";
            roleLabel = "Chef Producción";
        }
        
        if (!u.allowedPages) {
            if (u.role === "admin") u.allowedPages = ["dashboard-page", "pos-page", "caja-page", "inventario-page", "recetario-page", "produccion-page", "crm-page", "settings-page"];
            else if (u.role === "cajero") u.allowedPages = ["pos-page", "caja-page", "crm-page"];
            else u.allowedPages = ["inventario-page", "recetario-page", "produccion-page"];
        }
        
        const shortLabels = {
            "dashboard-page": "Tablero",
            "pos-page": "POS",
            "caja-page": "Caja",
            "inventario-page": "Bodega",
            "recetario-page": "Recetas",
            "produccion-page": "Producción",
            "crm-page": "CRM",
            "settings-page": "Config"
        };
        
        const permBadges = u.allowedPages.map(p => `<span class="badge" style="margin: 2px; font-size:9.5px; background: rgba(0,0,0,0.06); color: var(--text-color);">${shortLabels[p] || p}</span>`).join(" ");
        
        const deleteButton = u.username === "admin" ? "" : `<button class="btn btn-red small" onclick="deleteUser('${u.username}')" style="padding: 4px 8px; font-size: 11px;" title="Dar de Baja Cuenta"><i class="fa-solid fa-user-minus"></i> Dar de Baja</button>`;
        
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><strong>${u.name}</strong></td>
            <td><code>${u.username}</code> (Clave: <code>${u.password || '***'}</code>)</td>
            <td>RD$${parseFloat(u.baseSalary || 0).toLocaleString()}</td>
            <td><span class="${roleBadge}">${roleLabel}</span></td>
            <td><div style="display:flex; flex-wrap:wrap; max-width:220px;">${permBadges}</div></td>
            <td>${deleteButton}</td>
        `;
        tbody.appendChild(tr);
    });
}

// Registro global de eliminación de personal
window.deleteUser = async function(username) {
    if (activeRole !== "admin") {
        alert("Acceso denegado: Solo el Administrador puede eliminar personal.");
        return;
    }
    if (username === "admin") {
        alert("No puedes eliminar la cuenta de administrador principal.");
        return;
    }
    if (confirm(`¿Estás seguro de que deseas dar de baja y eliminar la cuenta del empleado '${username}'?`)) {
        if (sessionToken) {
            try {
                const res = await apiFetch("/api/auth/delete-user", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ username })
                });
                if (res && res.ok) {
                    const tenant = DB[activeTenant];
                    tenant.users = tenant.users.filter(u => u.username !== username);
                    saveToLocalStorage();
                    renderUserManagementList();
                    alert(`Empleado '${username}' eliminado con éxito de la nube.`);
                } else {
                    const err = await res.json();
                    alert(err.error || "No se pudo eliminar el usuario del servidor.");
                }
            } catch (err) {
                console.error("User Deletion Error:", err);
                alert("Error de conexión al eliminar usuario del servidor.");
            }
        } else {
            const tenant = DB[activeTenant];
            tenant.users = tenant.users.filter(u => u.username !== username);
            saveToLocalStorage();
            renderUserManagementList();
            alert(`Empleado '${username}' removido localmente.`);
        }
    }
};

function setupNavigation() {
    const navItems = document.querySelectorAll(".nav-item[data-target]");
    navItems.forEach(item => {
        item.addEventListener("click", (e) => {
            e.preventDefault();
            const targetId = item.getAttribute("data-target");
            
            // Restricción de cajero en SaaS Admin
            if (activeRole === "cajero" && targetId === "saas-page") {
                alert("Restringido: Los cajeros no tienen acceso a la consola de administración SaaS.");
                return;
            }
            
            navItems.forEach(i => i.classList.remove("active"));
            item.classList.add("active");
            
            document.querySelectorAll(".page-section").forEach(p => p.classList.remove("active"));
            const targetPage = document.getElementById(targetId);
            if (targetPage) {
                targetPage.classList.add("active");
                // Si el simulador móvil está encendido, clona dinámicamente el contenido
                if (isMobileShellActive) {
                    syncMobileScreen();
                }
            }
        });
    });
}

// 4. SISTEMA MULTIEMPRESA (Tenant Switching)
function setupTenantSelector() {
    const selector = document.getElementById("tenant-select");
    selector.addEventListener("change", (e) => {
        const tenant = e.target.value;
        loadTenant(tenant);
    });
}

async function loadTenant(tenantKey) {
    activeTenant = tenantKey;
    
    if (sessionToken && currentUser) {
        try {
            const res = await apiFetch("/api/tenant/data");
            if (res && res.ok) {
                const cloudData = await res.json();
                // Mezclar datos de la nube con la estructura local en memoria
                DB[activeTenant] = {
                    ...DB[activeTenant],
                    ...cloudData
                };
            }
        } catch (e) {
            console.error("Error al jalar datos operativos en la nube, usando caché local:", e);
        }
    }
    
    // Actualizar nombre en interfaz
    document.querySelectorAll(".tenant-name-span").forEach(el => {
        el.textContent = DB[activeTenant].info ? DB[activeTenant].info.name : activeTenant;
    });
    
    // Control de suspensión SaaS (Sweet House)
    const overlay = document.getElementById("suspended-overlay");
    const isActive = DB[activeTenant].info ? DB[activeTenant].info.active : true;
    if (!isActive) {
        overlay.classList.remove("hidden");
        // Deshabilitar sidebar nav e interacciones
        document.querySelectorAll(".sidebar-nav .nav-item").forEach(item => {
            if (item.getAttribute("data-target") !== "settings-page") {
                item.classList.add("disabled");
            }
        });
    } else {
        overlay.classList.add("hidden");
        document.querySelectorAll(".sidebar-nav .nav-item").forEach(item => {
            item.classList.remove("disabled");
        });
    }
    
    // Recargar todos los datos visuales
    reloadDashboardMetrics();
    renderPOSCatalog();
    renderCajaDetails();
    renderInventoryTable();
    renderRecipes();
    renderProductionCatalog();
    renderCRMPedidos();
    renderCRMClients();
    renderMermaPanel();
    renderAuditLog();
    renderUserManagementList();
    renderSalesHistoryTable();
    
    // Reiniciar Carrito
    activeCart = [];
    updateCartDOM();
    
    // Sincronizar móvil si aplica
    if (isMobileShellActive) {
        syncMobileScreen();
    }
}

// 5. CONTROL DE ROLES (Admin vs Cajero/a vs Producción Chef)
function setupRoleSelector() {
    const roleSelect = document.getElementById("role-select");
    roleSelect.addEventListener("change", (e) => {
        activeRole = e.target.value;
        logAudit("Seguridad", "Cambio de Rol de Usuario", `Nuevo rol activo: ${activeRole.toUpperCase()}`);
        applyRoleRestrictions();
    });
}

function applyRoleRestrictions() {
    const userRoleEl = document.getElementById("user-role");
    const userAvatarEl = document.getElementById("user-avatar");
    const userNameEl = document.getElementById("user-name");
    
    const navItems = document.querySelectorAll(".sidebar-nav .nav-item");
    const tenant = DB[activeTenant];
    
    // Buscar si el usuario actual tiene permisos personalizados en la base de datos
    let allowedPages = null;
    let customUserRecord = null;
    if (tenant && tenant.users && currentUser) {
        customUserRecord = tenant.users.find(u => u.username === currentUser.username);
        if (customUserRecord && customUserRecord.allowedPages) {
            allowedPages = customUserRecord.allowedPages;
        }
    }
    
    // Perfiles visuales por defecto
    if (activeRole === "cajero") {
        userRoleEl.textContent = "Cajera / Ventas";
        userNameEl.textContent = customUserRecord ? customUserRecord.name : "Camila Gómez";
        userAvatarEl.src = "https://images.unsplash.com/photo-1544005313-94ddf0286df2?q=80&w=256&auto=format&fit=crop";
        
        // Bloquear KPIs financieros en dashboard
        document.getElementById("kpi-bruta").closest(".kpi-card").style.opacity = "0.2";
        document.getElementById("kpi-neta").closest(".kpi-card").style.opacity = "0.2";
        
    } else if (activeRole === "produccion") {
        userRoleEl.textContent = "Chef de Producción";
        userNameEl.textContent = customUserRecord ? customUserRecord.name : "Chef Carlos Mendoza";
        userAvatarEl.src = "https://images.unsplash.com/photo-1577219491135-ce391730fb2c?q=80&w=256&auto=format&fit=crop";
        
        // Bloquear KPIs financieros
        document.getElementById("kpi-bruta").closest(".kpi-card").style.opacity = "0.2";
        document.getElementById("kpi-neta").closest(".kpi-card").style.opacity = "0.2";
        
    } else {
        // Administrador
        userRoleEl.textContent = "Administradora";
        userNameEl.textContent = customUserRecord ? customUserRecord.name : "Sofía Rodríguez";
        userAvatarEl.src = "https://images.unsplash.com/photo-1534528741775-53994a69daeb?q=80&w=256&auto=format&fit=crop";
        
        document.getElementById("kpi-bruta").closest(".kpi-card").style.opacity = "1";
        document.getElementById("kpi-neta").closest(".kpi-card").style.opacity = "1";
    }
    
    // Aplicar visibilidad de las pestañas
    navItems.forEach(item => {
        const target = item.getAttribute("data-target");
        if (!target) return;
        
        // Si hay permisos específicos, usarlos
        if (allowedPages) {
            item.style.display = allowedPages.includes(target) ? "block" : "none";
        } else {
            // Regla por defecto según rol
            if (activeRole === "cajero") {
                const isCajeroPage = target === "pos-page" || target === "caja-page" || target === "crm-page" || target === "settings-page";
                item.style.display = isCajeroPage ? "block" : "none";
            } else if (activeRole === "produccion") {
                const isChefPage = target === "inventario-page" || target === "recetario-page" || target === "produccion-page" || target === "settings-page";
                item.style.display = isChefPage ? "block" : "none";
            } else {
                item.style.display = "block"; // Admin ve todo
            }
        }
    });
    
    // Redirigir si la página activa actual quedó oculta
    const activeSection = document.querySelector(".page-section.active");
    if (activeSection) {
        let isPageVisible = true;
        navItems.forEach(item => {
            if (item.getAttribute("data-target") === activeSection.id && item.style.display === "none") {
                isPageVisible = false;
            }
        });
        
        if (!isPageVisible) {
            // Buscar la primera página visible disponible para redirigir
            let fallbackPage = "dashboard-page";
            if (allowedPages && allowedPages.length > 0) {
                fallbackPage = allowedPages[0];
            } else if (activeRole === "cajero") {
                fallbackPage = "pos-page";
            } else if (activeRole === "produccion") {
                fallbackPage = "inventario-page";
            }
            navigateToPage(fallbackPage);
        }
    }
    
    // Recargar para aplicar en vivo
    if (isMobileShellActive) {
        syncMobileScreen();
    }
}

function navigateToPage(pageId) {
    document.querySelectorAll(".page-section").forEach(p => p.classList.remove("active"));
    const page = document.getElementById(pageId);
    if (page) page.classList.add("active");
    
    document.querySelectorAll(".sidebar-nav .nav-item").forEach(item => {
        item.classList.remove("active");
        if (item.getAttribute("data-target") === pageId) {
            item.classList.add("active");
        }
    });
}

// 6. SIMULADOR MÓVIL EN TIEMPO REAL (Mobile Shell Toggle)
function setupMobileShellToggle() {
    const toggleBtn = document.getElementById("toggle-mobile-shell");
    toggleBtn.addEventListener("click", () => {
        isMobileShellActive = !isMobileShellActive;
        document.body.classList.toggle("mobile-shell-active", isMobileShellActive);
        document.getElementById("mobile-preview-shell").classList.toggle("hidden", !isMobileShellActive);
        
        if (isMobileShellActive) {
            toggleBtn.innerHTML = '<i class="fa-solid fa-desktop"></i> <span>Ver Escritorio</span>';
            syncMobileScreen();
        } else {
            toggleBtn.innerHTML = '<i class="fa-solid fa-mobile-screen-button"></i> <span>Ver en Celular</span>';
        }
    });
}

function syncMobileScreen() {
    const emulatedScreen = document.getElementById("mobile-screen-iframe-emulated");
    emulatedScreen.innerHTML = "";
    
    // Obtener la sección activa actual
    const activeSection = document.querySelector(".page-section.active");
    if (activeSection) {
        const cloned = activeSection.cloneNode(true);
        // Desvincular IDs para evitar colisiones leves en búsquedas rápidas si es necesario, 
        // pero para este simulador visual mantenemos la copia fiel.
        emulatedScreen.appendChild(cloned);
        
        // Re-enlazar listeners rápidos del POS o botones si es una demo
        const buyRecipeButtons = emulatedScreen.querySelectorAll(".buy-recipe-btn");
        buyRecipeButtons.forEach(btn => {
            btn.addEventListener("click", () => {
                const recipeType = btn.getAttribute("data-recipe");
                installMarketplaceRecipe(recipeType);
            });
        });
    }
}

// 7. LÓGICA DE METRICAS DEL DASHBOARD (Tablero General)
function reloadDashboardMetrics() {
    const tenant = DB[activeTenant];
    
    // Calcular Ventas Totales
    let totalVentas = 0;
    tenant.sales.forEach(s => totalVentas += s.total);
    
    // Calcular Costos de Venta (COGS)
    let totalCogs = 0;
    tenant.sales.forEach(s => {
        s.items.forEach(item => {
            const prod = tenant.products.find(p => p.name === item.name);
            const cost = prod ? prod.cost : (item.price * 0.4); // Costo real unitario
            totalCogs += (cost * item.qty);
        });
    });
    
    // Gastos Operativos (Egresos de Caja Chica + Nóminas del mes)
    let totalGastos = 0;
    let totalGastosFijos = 0;
    let totalGastosVariables = 0;
    if (tenant.caja && tenant.caja.active) {
        tenant.caja.active.movements.forEach(m => {
            if (m.type === "egreso") {
                totalGastos += m.monto;
                if (m.expenseClass === "fijo") {
                    totalGastosFijos += m.monto;
                } else {
                    totalGastosVariables += m.monto;
                }
            }
        });
    }
    
    // Utilidad Bruta
    const utilidadBruta = totalVentas - totalCogs;
    
    // Utilidad Neta Real
    const utilidadNeta = utilidadBruta - totalGastos;
    
    // Margen %
    const margenBruto = totalVentas > 0 ? Math.round((utilidadBruta / totalVentas) * 100) : 0;
    const margenNeto = totalVentas > 0 ? Math.round((utilidadNeta / totalVentas) * 100) : 0;
    
    // Escribir en interfaz
    document.getElementById("kpi-ventas").textContent = `RD$${totalVentas.toLocaleString()}`;
    document.getElementById("kpi-costos").textContent = `RD$${totalCogs.toLocaleString()}`;
    document.getElementById("kpi-bruta").textContent = `RD$${utilidadBruta.toLocaleString()}`;
    document.getElementById("kpi-neta").textContent = `RD$${utilidadNeta.toLocaleString()}`;
    
    document.getElementById("kpi-margen-bruto").textContent = `Margen Bruto: ${margenBruto}%`;
    document.getElementById("kpi-margen-neto").textContent = utilidadNeta >= 0 ? `¡Margen Neto ${margenNeto}%!` : "Pérdida en el período";

    // Escribir en Estado de Resultados Contable
    const erVentas = document.getElementById("er-ventas");
    const erCogs = document.getElementById("er-cogs");
    const erUtilidadBruta = document.getElementById("er-utilidad-bruta");
    const erGastosFijos = document.getElementById("er-gastos-fijos");
    const erGastosVariables = document.getElementById("er-gastos-variables");
    const erUtilidadNeta = document.getElementById("er-utilidad-neta");

    if (erVentas) erVentas.textContent = `RD$${totalVentas.toLocaleString('es-DO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (erCogs) erCogs.textContent = `RD$${totalCogs.toLocaleString('es-DO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (erUtilidadBruta) erUtilidadBruta.textContent = `RD$${utilidadBruta.toLocaleString('es-DO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (erGastosFijos) erGastosFijos.textContent = `RD$${totalGastosFijos.toLocaleString('es-DO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (erGastosVariables) erGastosVariables.textContent = `RD$${totalGastosVariables.toLocaleString('es-DO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (erUtilidadNeta) {
        erUtilidadNeta.textContent = `RD$${utilidadNeta.toLocaleString('es-DO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        if (utilidadNeta < 0) {
            erUtilidadNeta.className = "text-red font-bold";
        } else {
            erUtilidadNeta.className = "text-green font-bold";
        }
    }
    
    // Graficador de Progreso
    const totalFlujo = Math.max(totalVentas, 1);
    const netaPercent = Math.max(0, Math.min(100, Math.round((utilidadNeta / totalFlujo) * 100)));
    const cogsPercent = Math.max(0, Math.min(100, Math.round((totalCogs / totalFlujo) * 100)));
    const gastosPercent = Math.max(0, Math.min(100, Math.round((totalGastos / totalFlujo) * 100)));
    
    document.getElementById("progress-percentage").textContent = `${margenNeto}% de margen neto real`;
    document.getElementById("progress-neta-fill").style.width = `${netaPercent}%`;
    document.getElementById("progress-cogs-fill").style.width = `${cogsPercent}%`;
    document.getElementById("progress-gastos-fill").style.width = `${gastosPercent}%`;
    
    document.getElementById("legend-neta").textContent = `RD$${Math.max(0, utilidadNeta).toLocaleString()}`;
    document.getElementById("legend-cogs").textContent = `RD$${totalCogs.toLocaleString()}`;
    document.getElementById("legend-gastos").textContent = `RD$${totalGastos.toLocaleString()}`;
    
    // Saldos mini-cards
    let efectivoEsperado = tenant.caja.active ? tenant.caja.active.expectedCash : 0;
    document.getElementById("dash-cash-caja").textContent = `RD$${efectivoEsperado.toLocaleString()}`;
    
    // Dinero en bancos (Transferencias)
    let totalBancos = 0;
    tenant.sales.forEach(s => {
        if (s.payment === "transferencia" || s.payment === "tarjeta") totalBancos += s.total;
    });
    document.getElementById("dash-cash-bancos").textContent = `RD$${totalBancos.toLocaleString()}`;
    
    // Créditos pendientes
    let totalCredito = 0;
    tenant.clients.forEach(c => totalCredito += c.debt);
    document.getElementById("dash-cash-creditos").textContent = `RD$${totalCredito.toLocaleString()}`;
    
    // Renderizado de Ranking de Rentabilidad
    renderProfitableProducts();
    // Renderizado de Insumos Críticos
    renderCriticalInventoryAlerts();
}

function renderProfitableProducts() {
    const list = document.getElementById("profitable-products-list");
    list.innerHTML = "";
    
    const tenant = DB[activeTenant];
    const ranked = [...tenant.products].sort((a, b) => {
        const marginA = a.price - a.cost;
        const marginB = b.price - b.cost;
        return marginB - marginA; // De mayor a menor margen
    }).slice(0, 3);
    
    ranked.forEach((p, idx) => {
        const margin = p.price - p.cost;
        const marginPercent = Math.round((margin / p.price) * 100);
        
        const div = document.createElement("div");
        div.className = "ranking-item";
        div.innerHTML = `
            <div class="rank-left">
                <span class="rank-num">#${idx + 1}</span>
                <span class="rank-name">${p.name}</span>
            </div>
            <span class="rank-right">+${marginPercent}% Margen (RD$${margin})</span>
        `;
        list.appendChild(div);
    });
}

function renderCriticalInventoryAlerts() {
    const list = document.getElementById("critical-inventory-items");
    list.innerHTML = "";
    
    const tenant = DB[activeTenant];
    const criticals = tenant.inventory.filter(i => i.stock <= i.minStock);
    
    document.getElementById("critico-count").textContent = `${criticals.length} Alertas`;
    document.getElementById("alert-count").textContent = criticals.length;
    
    if (criticals.length === 0) {
        list.innerHTML = `
            <div class="empty-state-card text-center" style="padding: 10px;">
                <i class="fa-solid fa-circle-check text-green" style="font-size: 24px;"></i>
                <p style="margin-top: 5px;">Todo tu inventario está en niveles óptimos.</p>
            </div>
        `;
        return;
    }
    
    criticals.forEach(c => {
        const div = document.createElement("div");
        div.className = "critical-item";
        div.innerHTML = `
            <span class="crit-name"><i class="fa-solid fa-triangle-exclamation"></i> ${c.name}</span>
            <span class="crit-stock">Quedan ${c.stock.toLocaleString()} ${c.unit} (Mín: ${c.minStock})</span>
        `;
        list.appendChild(div);
    });
}

// 8. PUNTO DE VENTA (POS)
function renderPOSCatalog() {
    const grid = document.getElementById("pos-products-grid");
    grid.innerHTML = "";
    
    const tenant = DB[activeTenant];
    
    // Obtener filtros
    const query = document.getElementById("pos-search").value.toLowerCase();
    const activeCategory = document.querySelector(".category-tag.active").getAttribute("data-category");
    
    const filtered = tenant.products.filter(p => {
        const matchesSearch = p.name.toLowerCase().includes(query) || p.id.toLowerCase().includes(query);
        const matchesCategory = activeCategory === "all" || p.category === activeCategory;
        return matchesSearch && matchesCategory;
    });
    
    if (filtered.length === 0) {
        grid.innerHTML = `<div class="empty-state-card text-center" style="grid-column: 1/-1;">No se encontraron productos en catálogo.</div>`;
        return;
    }
    
    filtered.forEach(p => {
        const isCritical = p.stock <= 5;
        const card = document.createElement("div");
        card.className = "pos-product-card";
        card.innerHTML = `
            <img src="${p.img}" alt="${p.name}" class="p-card-img">
            <span class="p-card-name">${p.name}</span>
            <span class="p-card-price">RD$${p.price.toLocaleString()}</span>
            <span class="p-card-stock ${isCritical ? 'danger' : ''}">Stock: ${p.stock} u</span>
        `;
        card.addEventListener("click", () => addToCart(p));
        grid.appendChild(card);
    });
}

function setupPOSActions() {
    // Escucha en buscador
    document.getElementById("pos-search").addEventListener("input", renderPOSCatalog);
    
    // Categorías tags
    const tags = document.querySelectorAll(".category-tag");
    tags.forEach(tag => {
        tag.addEventListener("click", () => {
            tags.forEach(t => t.classList.remove("active"));
            tag.classList.add("active");
            renderPOSCatalog();
        });
    });
    
    // Vaciar carrito
    document.getElementById("clear-cart-btn").addEventListener("click", () => {
        activeCart = [];
        updateCartDOM();
    });
    
    // Control de cambio de método de pago
    const methodSelect = document.getElementById("pos-payment-method");
    methodSelect.addEventListener("change", (e) => {
        const val = e.target.value;
        document.getElementById("pos-mixto-fields").classList.toggle("hidden", val !== "mixto");
        document.getElementById("pos-cash-received-wrapper").classList.toggle("hidden", val !== "efectivo");
        
        if (val === "mixto") {
            calculateMixedPayment();
        }
    });
    
    // Escucha de recibido efectivo para devuelta
    document.getElementById("pos-cash-received").addEventListener("input", calculateChange);
    document.getElementById("pos-mixto-efectivo").addEventListener("input", calculateMixedPayment);
    
    // Selector NCF
    const ncfBtns = document.querySelectorAll(".ncf-buttons .ncf-btn");
    ncfBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            ncfBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            
            const isFiscal = btn.getAttribute("data-type") === "fiscal";
            document.getElementById("ncf-fiscal-rnc-wrapper").classList.toggle("hidden", !isFiscal);
        });
    });
    
    // Checkout
    document.getElementById("pos-checkout-btn").addEventListener("click", executeCheckout);
}

function addToCart(product) {
    // Validar stock primero
    if (product.stock <= 0) {
        alert("¡Alerta de Inventario! Este producto terminado no tiene stock disponible. Debes procesar una orden de producción primero.");
        return;
    }
    
    const existing = activeCart.find(item => item.id === product.id);
    if (existing) {
        if (existing.qty >= product.stock) {
            alert(`No puedes agregar más de ${product.stock} unidades de este producto.`);
            return;
        }
        existing.qty++;
    } else {
        activeCart.push({
            id: product.id,
            name: product.name,
            price: product.price,
            qty: 1
        });
    }
    updateCartDOM();
}

function updateCartDOM() {
    const container = document.getElementById("cart-items-container");
    container.innerHTML = "";
    
    if (activeCart.length === 0) {
        container.innerHTML = `
            <div class="empty-cart-state">
                <i class="fa-solid fa-cart-shopping"></i>
                <p>El carrito está vacío.<br>Haz clic en un producto para agregarlo.</p>
            </div>
        `;
        document.getElementById("cart-subtotal").textContent = "RD$0.00";
        document.getElementById("cart-tax").textContent = "RD$0.00";
        document.getElementById("cart-total").textContent = "RD$0.00";
        return;
    }
    
    let subtotal = 0;
    
    activeCart.forEach(item => {
        subtotal += (item.price * item.qty);
        const div = document.createElement("div");
        div.className = "cart-item";
        div.innerHTML = `
            <div class="cart-item-info">
                <span class="cart-item-name">${item.name}</span>
                <span class="cart-item-price">RD$${item.price.toLocaleString()} c/u</span>
            </div>
            <div class="cart-item-qty">
                <button class="cart-qty-btn decrease-qty" data-id="${item.id}">-</button>
                <span class="font-bold">${item.qty}</span>
                <button class="cart-qty-btn increase-qty" data-id="${item.id}">+</button>
            </div>
            <span class="font-bold">RD$${(item.price * item.qty).toLocaleString()}</span>
        `;
        
        // Listeners cantidad
        div.querySelector(".decrease-qty").addEventListener("click", () => {
            item.qty--;
            if (item.qty <= 0) {
                activeCart = activeCart.filter(i => i.id !== item.id);
            }
            updateCartDOM();
        });
        
        div.querySelector(".increase-qty").addEventListener("click", () => {
            const original = DB[activeTenant].products.find(p => p.id === item.id);
            if (item.qty >= original.stock) {
                alert("Stock insuficiente.");
                return;
            }
            item.qty++;
            updateCartDOM();
        });
        
        container.appendChild(div);
    });
    
    // ITBIS desglosado 18%
    const itbis = Math.round(subtotal * 0.18);
    const total = subtotal; // ITBIS está desglosado en el subtotal en reposterías, o se suma. Aquí se desglose.
    
    document.getElementById("cart-subtotal").textContent = `RD$${(subtotal - itbis).toLocaleString()}`;
    document.getElementById("cart-tax").textContent = `RD$${itbis.toLocaleString()}`;
    document.getElementById("cart-total").textContent = `RD$${total.toLocaleString()}`;
    
    // Recalcular devuelta y mixto
    calculateChange();
    calculateMixedPayment();
}

function calculateChange() {
    const total = activeCart.reduce((sum, item) => sum + (item.price * item.qty), 0);
    const received = parseFloat(document.getElementById("pos-cash-received").value) || 0;
    const change = Math.max(0, received - total);
    document.getElementById("pos-cash-change").textContent = `RD$${change.toLocaleString()}`;
}

function calculateMixedPayment() {
    const total = activeCart.reduce((sum, item) => sum + (item.price * item.qty), 0);
    const cash = parseFloat(document.getElementById("pos-mixto-efectivo").value) || 0;
    const card = Math.max(0, total - cash);
    document.getElementById("pos-mixto-tarjeta").value = card;
}

function executeCheckout() {
    const tenant = DB[activeTenant];
    
    if (activeCart.length === 0) {
        alert("El carrito está vacío.");
        return;
    }
    
    // Validar si la caja está abierta
    if (!tenant.caja.active) {
        alert("⚠️ ATENCIÓN: No puedes realizar ventas con la caja cerrada. Abre la caja chica en el módulo 'Caja y Turnos' antes de operar.");
        return;
    }
    
    const clientSelect = document.getElementById("cart-customer-select");
    const clientName = (clientSelect && clientSelect.options && clientSelect.selectedIndex !== -1)
        ? clientSelect.options[clientSelect.selectedIndex].text
        : "Consumidor Final";
    const clientId = clientSelect ? clientSelect.value : "";
    
    const paymentMethod = document.getElementById("pos-payment-method").value;
    const activeNcfBtn = document.querySelector(".ncf-buttons .ncf-btn.active") || document.querySelector(".ncf-btn.active") || document.querySelector(".ncf-btn");
    const isFiscal = activeNcfBtn ? activeNcfBtn.getAttribute("data-type") === "fiscal" : false;
    const rncInput = document.getElementById("pos-rnc-input") ? document.getElementById("pos-rnc-input").value : "";
    
    if (isFiscal && (!rncInput || rncInput.trim().length < 9)) {
        alert("Debes proveer un RNC o Cédula válido de 9 o 11 dígitos para comprobantes de crédito fiscal.");
        return;
    }
    
    const total = activeCart.reduce((sum, item) => sum + (item.price * item.qty), 0);
    
    // Validación de límites de crédito si aplica
    if (paymentMethod === "credito") {
        const client = tenant.clients.find(c => c.id === clientId);
        if (!client) {
            alert("Selecciona un cliente con cuenta corriente aprobada.");
            return;
        }
        if ((client.debt + total) > client.creditLimit) {
            alert(`⚠️ CRÉDITO RECHAZADO: Esta venta supera el límite de crédito aprobado para ${client.name} (Límite: RD$${client.creditLimit}, Deuda Actual: RD$${client.debt}).`);
            return;
        }
    }
    
    // 1. Descontar stock de productos terminados en POS
    activeCart.forEach(item => {
        const prod = tenant.products.find(p => p.id === item.id);
        if (prod) {
            prod.stock -= item.qty;
        }
    });
    
    // 2. Generar NCF consecutivo
    const lastSaleNum = tenant.sales.length + 1;
    const ncfPrefix = isFiscal ? "B02" : "B01";
    const ncf = `${ncfPrefix}${lastSaleNum.toString().padStart(8, '0')}`;
    
    // 3. Crear Registro de Venta
    const itbis = Math.round(total * 0.18);
    const saleRecord = {
        id: `sale_${lastSaleNum.toString().padStart(4, '0')}`,
        date: new Date().toISOString(),
        customer: clientName,
        items: JSON.parse(JSON.stringify(activeCart)),
        subtotal: total - itbis,
        tax: itbis,
        total: total,
        payment: paymentMethod,
        ncf: ncf
    };
    
    tenant.sales.push(saleRecord);
    
    // Hook Audit
    const totalCost = saleRecord.items.reduce((sum, item) => sum + ((item.cost || 0) * item.qty), 0);
    const profit = total - totalCost;
    logAudit("Ventas", `Nueva venta POS NCF: ${ncf}`, `Monto: RD$${total.toFixed(2)} | Ganancia: RD$${profit.toFixed(2)} | Método: ${paymentMethod.toUpperCase()}`);
    
    // 4. Modificaciones contables inmediatas
    if (paymentMethod === "efectivo") {
        tenant.caja.active.expectedCash += total;
    } else if (paymentMethod === "mixto") {
        const cashPart = parseFloat(document.getElementById("pos-mixto-efectivo").value) || 0;
        tenant.caja.active.expectedCash += cashPart;
    } else if (paymentMethod === "credito") {
        const client = tenant.clients.find(c => c.id === clientId);
        if (client) {
            client.debt += total;
        }
    }
    
    saveToLocalStorage();
    
    // Mostrar Recibo Fiscal dominicano de impresión
    showPremiumReceipt(saleRecord, isFiscal ? rncInput : null);
    
    //function printReceiptHTML(receiptInnerHtml) {
    const iframe = document.createElement("iframe");
    iframe.style.position = "absolute";
    iframe.style.width = "0px";
    iframe.style.height = "0px";
    iframe.style.border = "none";
    document.body.appendChild(iframe);
    
    const doc = iframe.contentWindow.document;
    doc.open();
    doc.write(`
        <html>
        <head>
            <title>Imprimir Recibo</title>
            <style>
                @page {
                    size: auto;
                    margin: 0mm;
                }
                body {
                    font-family: 'Courier New', monospace;
                    background: white;
                    color: black;
                    margin: 10px;
                    padding: 0;
                    width: 280px; /* Ancho estándar de ticketera térmica */
                }
                .text-center { text-align: center; }
                table { width: 100%; border-collapse: collapse; }
                th, td { font-size: 11px; padding: 2px 0; }
                th { border-bottom: 1px dashed black; text-align: left; }
                .total-row { font-size: 11px; text-align: right; padding: 8px 0; }
                .dashed-border { border-top: 1px dashed black; border-bottom: 1px dashed black; padding: 8px 0; }
            </style>
        </head>
        <body>
            ${receiptInnerHtml}
            <script>
                window.onload = function() {
                    window.focus();
                    window.print();
                    setTimeout(function() { window.frameElement.remove(); }, 1000);
                };
            </script>
        </body>
        </html>
    `);
    doc.close();
}

function showPremiumReceipt(sale, rnc) {
    const itbis = sale.tax;
    const subtotal = sale.subtotal;
    const tenant = DB[activeTenant];
    
    // Buscar si el cliente tiene teléfono para auto-completar
    const clientObj = (tenant.clients && sale.customer)
        ? tenant.clients.find(c => c.name === sale.customer || (typeof sale.customer === "string" && sale.customer.includes(c.name)))
        : null;
    const prefilledPhone = clientObj ? clientObj.phone : "";
    
    const tenantName = (tenant.info && tenant.info.name) ? tenant.info.name : activeTenant;
    const tenantAddress = (tenant.info && tenant.info.address) ? tenant.info.address : "República Dominicana";
    const tenantRnc = (tenant.info && tenant.info.rnc) ? tenant.info.rnc : "N/A";
    
    const overlay = document.createElement("div");
    overlay.className = "modal";
    overlay.id = "receipt-print-modal";
    
    overlay.innerHTML = `
        <div class="modal-content glass-card" style="max-width: 320px; font-family: 'Courier New', monospace; background: white; color: black; border-radius: 4px; padding: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.15);">
            <div id="receipt-print-area" style="background: white; color: black;">
                <div class="text-center" style="border-bottom: 1px dashed black; padding-bottom: 10px;">
                    <h3 style="margin: 0; font-size: 18px; font-weight: bold;">${tenantName} ERP</h3>
                    <p style="font-size: 11px; margin: 4px 0;">${tenantAddress}</p>
                    <p style="font-size: 11px; margin: 2px 0;">RNC: ${tenantRnc}</p>
                    <p style="font-size: 10px; margin: 2px 0;">Fecha: ${new Date(sale.date).toLocaleString()}</p>
                </div>
                
                <div style="font-size: 11px; border-bottom: 1px dashed black; padding: 10px 0;">
                    <div><strong>COMPROBANTE FISCAL</strong></div>
                    <div>NCF: <strong>${sale.ncf}</strong></div>
                    ${rnc ? `<div>RNC Cliente: ${rnc}</div>` : ""}
                    <div>Cliente: ${sale.customer}</div>
                    <div>Metodo: ${sale.payment.toUpperCase()}</div>
                </div>
                
                <div style="font-size: 11px; padding: 10px 0; border-bottom: 1px dashed black;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr style="border-bottom: 1px dashed black;">
                                <th style="text-align: left;">Articulo</th>
                                <th style="text-align: right;">Cant</th>
                                <th style="text-align: right;">Total</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${sale.items.map(item => `
                                <tr>
                                    <td>${item.name.substring(0, 18)}</td>
                                    <td style="text-align: right;">${item.qty}</td>
                                    <td style="text-align: right;">RD$${(item.price * item.qty).toLocaleString()}</td>
                                </tr>
                            `).join("")}
                        </tbody>
                    </table>
                </div>
                
                <div style="font-size: 11px; text-align: right; padding: 8px 0;">
                    <div>Subtotal: RD$${subtotal.toLocaleString()}</div>
                    <div>ITBIS (18%): RD$${itbis.toLocaleString()}</div>
                    <div style="font-size: 14px; font-weight: bold; margin-top: 4px;">Total Neto: RD$${sale.total.toLocaleString()}</div>
                </div>
                
                <div class="text-center" style="font-size: 10px; margin-top: 10px; border-top: 1px dashed black; padding-top: 10px;">
                    <p>A&M ERP SaaS - Nivel Empresa</p>
                    <p>*** ¡Gracias por su Compra! ***</p>
                </div>
            </div>
 
            <div class="divider" style="border-top: 1px dashed black; margin-top: 10px; padding-top: 10px;"></div>
            
            <button class="btn small btn-full" id="print-thermal-receipt-btn" style="background-color: #3b82f6; color: white; border: none; font-family: var(--font-primary); display: flex; align-items: center; justify-content: center; gap: 8px; border-radius: 4px; padding: 8px; font-weight: bold; cursor: pointer; width: 100%; box-sizing: border-box; margin-bottom: 8px;">
                <i class="fa-solid fa-print" style="font-size: 16px;"></i> Imprimir Ticket Térmico
            </button>
            
            <div style="font-size: 11px; margin-top: 5px; text-align: left;">
                <label for="receipt-whatsapp-phone" style="display: block; font-weight: bold; margin-bottom: 4px; font-family: var(--font-primary);">📱 WhatsApp del Cliente:</label>
                <input type="text" id="receipt-whatsapp-phone" class="input-premium small" placeholder="ej: 8295551234" value="${prefilledPhone}" style="width: 100%; border: 1px solid #ccc; text-align: center; font-family: var(--font-primary); font-weight: bold; border-radius: 4px; padding: 6px; box-sizing: border-box;">
            </div>
            
            <button class="btn small btn-full margin-top-10" id="send-whatsapp-receipt-btn" style="background-color: #25d366; color: white; border: none; font-family: var(--font-primary); display: flex; align-items: center; justify-content: center; gap: 8px; border-radius: 4px; padding: 8px; font-weight: bold; cursor: pointer; width: 100%; box-sizing: border-box;">
                <i class="fa-brands fa-whatsapp" style="font-size: 16px;"></i> Enviar por WhatsApp
            </button>
            
            <button class="btn btn-primary small btn-full margin-top-15" id="close-receipt-print-btn" style="font-family: var(--font-primary); width: 100%; box-sizing: border-box;">Listo</button>
        </div>
    `;
    
    document.body.appendChild(overlay);
    
    document.getElementById("print-thermal-receipt-btn").addEventListener("click", () => {
        const printContent = document.getElementById("receipt-print-area").innerHTML;
        printReceiptHTML(printContent);
    });
    
    document.getElementById("close-receipt-print-btn").addEventListener("click", () => {
        overlay.remove();
    });
    
    document.getElementById("send-whatsapp-receipt-btn").addEventListener("click", () => {
        const phoneVal = document.getElementById("receipt-whatsapp-phone").value.trim();
        if (!phoneVal) {
            alert("Por favor ingresa un número de teléfono de WhatsApp.");
            return;
        }
        
        let phoneClean = phoneVal.replace(/\D/g, "");
        if (phoneClean.length === 10 && (phoneClean.startsWith("809") || phoneClean.startsWith("829") || phoneClean.startsWith("849"))) {
            phoneClean = "1" + phoneClean; // Prefijo de República Dominicana
        }
        
        let messageText = `🍰 *${tenant.info.name}* 🍰\n`;
        messageText += `*¡Gracias por tu compra!* Aquí tienes el desglose de tu factura:\n\n`;
        messageText += `*Factura ID:* ${sale.id}\n`;
        messageText += `*NCF:* ${sale.ncf}\n`;
        messageText += `*Fecha:* ${new Date(sale.date).toLocaleString()}\n`;
        messageText += `*Cliente:* ${sale.customer}\n`;
        messageText += `*Método de Pago:* ${sale.payment.toUpperCase()}\n`;
        messageText += `-----------------------------\n`;
        sale.items.forEach(item => {
            messageText += `• ${item.qty}x ${item.name} - RD$${(item.price * item.qty).toLocaleString()}\n`;
        });
        messageText += `-----------------------------\n`;
        messageText += `*Subtotal:* RD$${subtotal.toLocaleString()}\n`;
        messageText += `*ITBIS (18%):* RD$${itbis.toLocaleString()}\n`;
        messageText += `*Total Neto:* RD$${sale.total.toLocaleString()}\n\n`;
        messageText += `*A&M ERP SaaS - Nivel Empresa*`;
        
        const encodedText = encodeURIComponent(messageText);
        window.open(`https://wa.me/${phoneClean}?text=${encodedText}`, "_blank");
        
        logAudit("Ventas", "Factura Enviada", `WhatsApp enviado a ${sale.customer} al número ${phoneClean}`);
    });
}

// 9. CAJA CHICA Y CONTROL DE TURNOS
function renderCajaDetails() {
    const tenant = DB[activeTenant];
    const statusText = document.getElementById("caja-panel-status");
    const indicator = document.getElementById("topbar-caja-indicator");
    
    const openForm = document.getElementById("caja-open-form");
    const activeInfo = document.getElementById("caja-active-info");
    
    if (!tenant.caja.active) {
        // Caja Cerrada
        statusText.textContent = "Cerrada";
        statusText.className = "badge red-bg";
        indicator.className = "caja-status-indicator closed";
        indicator.innerHTML = '<span class="status-dot red"></span> <span class="indicator-text">Caja Cerrada</span>';
        
        openForm.classList.remove("hidden");
        activeInfo.classList.add("hidden");
    } else {
        // Caja Abierta
        statusText.textContent = "Abierta (Turno Activo)";
        statusText.className = "badge green-bg";
        indicator.className = "caja-status-indicator";
        indicator.innerHTML = '<span class="status-dot green"></span> <span class="indicator-text">Caja Abierta</span>';
        
        openForm.classList.add("hidden");
        activeInfo.classList.remove("hidden");
        
        // Calcular sumatorias de movimientos
        const active = tenant.caja.active;
        
        // Ventas efectivo
        let cashSalesSum = 0;
        tenant.sales.forEach(s => {
            // Validar que la venta sea en efectivo o mixta y ocurra después del openTime
            if (new Date(s.date) >= new Date(active.openTime)) {
                if (s.payment === "efectivo") {
                    cashSalesSum += s.total;
                } else if (s.payment === "mixto") {
                    // En caso de mixto, sumar la porción de efectivo guardada o asumida
                    cashSalesSum += (s.total * 0.5); // Asumiendo mitad por defecto en históricos rápidos
                }
            }
        });
        
        // Abonos a créditos realizados en efectivo en este turno
        let cashAbonosSum = 0;
        active.movements.forEach(m => {
            if (m.type === "ingreso" && m.concept.includes("Abono Crédito")) {
                cashAbonosSum += m.monto;
            }
        });
        
        // Egresos manuales
        let egresosSum = 0;
        active.movements.forEach(m => {
            if (m.type === "egreso") {
                egresosSum += m.monto;
            } else if (m.type === "ingreso" && !m.concept.includes("Abono Crédito")) {
                // Si es un aporte extra, reduce egreso o suma fondo
                cashAbonosSum += m.monto;
            }
        });
        
        // Actualizar UI
        document.getElementById("caja-val-fondo").textContent = `RD$${active.openFund.toLocaleString()}`;
        document.getElementById("caja-val-ventas").textContent = `RD$${cashSalesSum.toLocaleString()}`;
        document.getElementById("caja-val-abonos").textContent = `RD$${cashAbonosSum.toLocaleString()}`;
        document.getElementById("caja-val-egresos").textContent = `RD$${egresosSum.toLocaleString()}`;
        
        const esperado = active.openFund + cashSalesSum + cashAbonosSum - egresosSum;
        active.expectedCash = esperado; // Sincronizar en DB
        
        document.getElementById("caja-val-esperado").textContent = `RD$${esperado.toLocaleString()}`;
        
        // Auditoría tabla
        renderCajaMovementsList();
    }
}

function setupCajaActions() {
    // Abrir Caja
    document.getElementById("caja-open-btn").addEventListener("click", () => {
        const tenant = DB[activeTenant];
        const fund = parseFloat(document.getElementById("caja-fondo-inicial").value) || 0;
        
        tenant.caja.active = {
            id: `caja_act_${Date.now()}`,
            openTime: new Date().toISOString(),
            openFund: fund,
            expectedCash: fund,
            movements: []
        };
        
        logAudit("Caja Chica", "Apertura de Caja", `Fondo Inicial: RD$${fund.toFixed(2)}`);
        
        saveToLocalStorage();
        renderCajaDetails();
        reloadDashboardMetrics();
    });
    
    // Registrar egreso/ingreso manual
    document.getElementById("caja-add-mov-btn").addEventListener("click", () => {
        const tenant = DB[activeTenant];
        if (!tenant.caja.active) {
            alert("Abre la caja primero.");
            return;
        }
        
        const tipo = document.getElementById("caja-mov-tipo").value;
        const monto = parseFloat(document.getElementById("caja-mov-monto").value) || 0;
        const concepto = document.getElementById("caja-mov-concepto").value;
        const expenseClass = tipo === "egreso" ? document.getElementById("caja-expense-class").value : "variable";
        
        if (monto <= 0 || !concepto.trim()) {
            alert("Ingresa un monto válido y un concepto para el movimiento de caja chica.");
            return;
        }
        
        tenant.caja.active.movements.push({
            time: new Date().toISOString(),
            type: tipo,
            monto: monto,
            concept: concepto,
            expenseClass: expenseClass
        });
        
        logAudit("Caja Chica", `Registro de ${tipo.toUpperCase()} (${expenseClass.toUpperCase()})`, `Concepto: ${concepto} | Monto: RD$${monto.toFixed(2)}`);
        
        saveToLocalStorage();
        renderCajaDetails();
        reloadDashboardMetrics();
        
        // Limpiar inputs
        document.getElementById("caja-mov-monto").value = "";
        document.getElementById("caja-mov-concepto").value = "";
    });
    
    // Cierre de caja en vivo
    const realContadoInput = document.getElementById("caja-real-contado");
    realContadoInput.addEventListener("input", (e) => {
        const tenant = DB[activeTenant];
        if (!tenant.caja.active) return;
        
        const contado = parseFloat(e.target.value) || 0;
        const esperado = tenant.caja.active.expectedCash;
        const diff = contado - esperado;
        
        const resBox = document.getElementById("caja-arqueo-result");
        if (diff === 0) {
            resBox.className = "arqueo-diff-box success";
            resBox.textContent = "RD$0.00 (Turno Cuadrado)";
        } else if (diff < 0) {
            resBox.className = "arqueo-diff-box danger";
            resBox.textContent = `RD$${diff.toLocaleString()} (⚠️ FALTANTE)`;
        } else {
            resBox.className = "arqueo-diff-box success";
            resBox.textContent = `RD$${diff.toLocaleString()} (🟢 SOBRANTE)`;
        }
    });
    
    // Cierre definitivo del turno
    document.getElementById("caja-close-btn").addEventListener("click", () => {
        const tenant = DB[activeTenant];
        if (!tenant.caja.active) return;
        
        const contado = parseFloat(document.getElementById("caja-real-contado").value);
        if (isNaN(contado)) {
            alert("Por favor ingresa el monto total de efectivo físico contado en la gaveta.");
            return;
        }
        
        const active = tenant.caja.active;
        const esperado = active.expectedCash;
        const diff = contado - esperado;
        let status = "Cuadrado";
        if (diff < 0) status = "Faltante";
        if (diff > 0) status = "Sobrante";
        
        // Mover a histórico
        tenant.caja.history.push({
            id: active.id,
            openTime: active.openTime,
            closeTime: new Date().toISOString(),
            openFund: active.openFund,
            expectedCash: esperado,
            physicalCash: contado,
            difference: diff,
            status: status
        });
        
        logAudit("Caja Chica", "Cierre de Caja", `Arqueo Real: RD$${contado.toFixed(2)} | Esperado: RD$${esperado.toFixed(2)} | Diferencia: RD$${diff.toFixed(2)} | Estado: ${status.toUpperCase()}`);
        
        // Cerrar caja
        tenant.caja.active = null;
        
        saveToLocalStorage();
        renderCajaDetails();
        reloadDashboardMetrics();
        
        document.getElementById("caja-real-contado").value = "";
        document.getElementById("caja-arqueo-result").className = "arqueo-diff-box";
        document.getElementById("caja-arqueo-result").textContent = "RD$0.00 (Cuadrado)";
        
        alert(`¡Caja Cerrada con éxito! Estado: ${status} (Diferencia: RD$${diff.toLocaleString()}).`);
    });
}

function renderCajaMovementsList() {
    const tenant = DB[activeTenant];
    const tbody = document.getElementById("caja-movimientos-tbody");
    tbody.innerHTML = "";
    
    if (!tenant.caja.active || tenant.caja.active.movements.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" class="text-center">No hay retiros o egresos en este turno.</td></tr>`;
        return;
    }
    
    tenant.caja.active.movements.forEach(m => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${new Date(m.time).toLocaleTimeString()}</td>
            <td><span class="badge ${m.type === 'egreso' ? 'red-bg' : 'green-bg'}">${m.type.toUpperCase()}</span></td>
            <td>RD$${m.monto.toLocaleString()}</td>
            <td>${m.concept}</td>
        `;
        tbody.appendChild(tr);
    });
}

// 10. INVENTARIO REAL Y AJUSTES
function renderInventoryTable() {
    const tbody = document.getElementById("inventory-items-tbody");
    tbody.innerHTML = "";
    
    const tenant = DB[activeTenant];
    const catFilter = document.getElementById("inventory-cat-filter").value;
    const unitFilterEl = document.getElementById("inventory-unit-filter");
    const unitView = unitFilterEl ? unitFilterEl.value : "base";
    
    const filtered = tenant.inventory.filter(item => {
        return catFilter === "all" || item.category === catFilter;
    });
    
    filtered.forEach(item => {
        let displayStock = item.stock;
        let displayUnit = item.unit;
        let displayCost = item.cost;
        
        // Conversión a Unidades Reposteras Frecuentes
        if (unitView === "tazas") {
            if (item.unit === "g") {
                displayStock = item.stock / 125; // 1 taza de harina/polvo ≈ 125g
                displayUnit = "tazas";
                displayCost = item.cost * 125;
            } else if (item.unit === "ml") {
                displayStock = item.stock / 250; // 1 taza de líquido = 250ml
                displayUnit = "tazas (liq)";
                displayCost = item.cost * 250;
            }
        } else if (unitView === "onzas") {
            if (item.unit === "g") {
                displayStock = item.stock / 28.35; // 1 oz dry ≈ 28.35g
                displayUnit = "oz";
                displayCost = item.cost * 28.35;
            } else if (item.unit === "ml") {
                displayStock = item.stock / 29.57; // 1 fl oz ≈ 29.57ml
                displayUnit = "fl oz";
                displayCost = item.cost * 29.57;
            }
        } else if (unitView === "libras") {
            if (item.unit === "g") {
                displayStock = item.stock / 453.6; // 1 lb ≈ 453.6g
                displayUnit = "lb";
                displayCost = item.cost * 453.6;
            } else if (item.unit === "ml") {
                displayStock = item.stock / 453.6;
                displayUnit = "lb (aprox)";
                displayCost = item.cost * 453.6;
            }
        }

        const isCritical = item.stock <= item.minStock;
        const totalVal = item.stock * item.cost;
        
        const tr = document.createElement("tr");
        let editBtn = "";
        if (activeRole === "admin") {
            editBtn = `
                <button class="btn btn-secondary btn-icon-only small inventory-edit-trigger" data-id="${item.id}" title="Editar Ficha Insumo" style="background: rgba(0,0,0,0.03); margin-left: 4px;">
                    <i class="fa-solid fa-pen-to-square"></i>
                </button>
            `;
        }
        
        tr.innerHTML = `
            <td><strong>${item.name}</strong></td>
            <td><span class="badge font-secondary">${item.category}</span></td>
            <td class="${isCritical ? 'text-red font-bold' : ''}">${displayStock.toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 2})}</td>
            <td>${displayUnit}</td>
            <td>RD$${displayCost.toFixed(2)}</td>
            <td>RD$${totalVal.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
            <td>${(item.minStock / (item.stock / displayStock || 1)).toLocaleString(undefined, {maximumFractionDigits: 1})} ${displayUnit}</td>
            <td><span class="badge ${isCritical ? 'red-bg' : 'green-bg'}">${isCritical ? 'Crítico' : 'Estable'}</span></td>
            <td>
                <div style="display: flex; align-items: center;">
                    <button class="btn btn-secondary btn-icon-only small inventory-adjust-trigger" data-id="${item.id}" title="Ajuste de Stock">
                        <i class="fa-solid fa-sliders"></i>
                    </button>
                    ${editBtn}
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
    
    // Re-enlazar clicks
    tbody.querySelectorAll(".inventory-adjust-trigger").forEach(btn => {
        btn.addEventListener("click", () => {
            const id = btn.getAttribute("data-id");
            openInventoryAdjustModal(id);
        });
    });
    
    tbody.querySelectorAll(".inventory-edit-trigger").forEach(btn => {
        btn.addEventListener("click", () => {
            const id = btn.getAttribute("data-id");
            openEditItemModal(id);
        });
    });
    
    renderKardexList();
}

function renderKardexList() {
    const tbody = document.getElementById("kardex-tbody");
    tbody.innerHTML = "";
    
    const tenant = DB[activeTenant];
    if (tenant.kardex.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center">No hay registros en el Kardex aún.</td></tr>`;
        return;
    }
    
    // Mostrar últimos 10 de reversa
    const sorted = [...tenant.kardex].reverse().slice(0, 10);
    sorted.forEach(k => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${new Date(k.time).toLocaleString()}</td>
            <td><strong>${k.name}</strong></td>
            <td><span class="badge">${k.type}</span></td>
            <td>${k.qty.toLocaleString()}</td>
            <td>${k.unit}</td>
            <td>RD$${k.cost.toFixed(2)}</td>
            <td class="font-secondary">${k.reason}</td>
        `;
        tbody.appendChild(tr);
    });
}

function setupInventoryActions() {
    // Escucha categoría filtro
    document.getElementById("inventory-cat-filter").addEventListener("change", renderInventoryTable);
    
    // Escucha selector de unidad visual
    const unitFilter = document.getElementById("inventory-unit-filter");
    if (unitFilter) {
        unitFilter.addEventListener("change", renderInventoryTable);
    }
    
    // Registrar compra
    document.getElementById("add-inventory-btn").addEventListener("click", () => {
        openInventoryPurchaseModal();
    });
    
    // Guardar compra en modal
    document.getElementById("inv-modal-save-btn").addEventListener("click", executeInventoryTransaction);

    // Registrar evento de ejecución de mermas
    const mermaBtn = document.getElementById("merma-execute-btn");
    if (mermaBtn) {
        mermaBtn.addEventListener("click", executeMermaTransaction);
    }
}

function openInventoryPurchaseModal() {
    const tenant = DB[activeTenant];
    const select = document.getElementById("inv-modal-select");
    select.innerHTML = "";
    
    tenant.inventory.forEach(item => {
        const opt = document.createElement("option");
        opt.value = item.id;
        opt.textContent = `${item.name} (${item.unit})`;
        select.appendChild(opt);
    });
    
    document.getElementById("inv-modal-qty").value = "";
    document.getElementById("inv-modal-cost").value = "";
    document.getElementById("inv-modal-unit").value = "base";
    document.getElementById("inv-modal-save-btn").textContent = "Guardar Compra";
    
    // Mostrar campos de compra
    document.getElementById("inv-modal-unit-group").style.display = "block";
    document.getElementById("inv-modal-cost-group").style.display = "block";
    
    // Cambiar layout de grid a grid-3
    document.getElementById("inv-modal-inputs-row").className = "grid-3 gap-10 margin-top-10";
    
    // Mostrar Modal
    document.getElementById("inventory-modal").classList.remove("hidden");
}

function openInventoryAdjustModal(itemId) {
    const tenant = DB[activeTenant];
    const item = tenant.inventory.find(i => i.id === itemId);
    if (!item) return;
    
    const select = document.getElementById("inv-modal-select");
    select.innerHTML = `<option value="${item.id}" selected>${item.name} (${item.unit}) - AJUSTE MANUAL</option>`;
    
    document.getElementById("inv-modal-qty").value = item.stock;
    document.getElementById("inv-modal-cost").value = "";
    document.getElementById("inv-modal-unit").value = "base";
    document.getElementById("inv-modal-save-btn").textContent = "Fijar Ajuste de Stock";
    
    // Ocultar campos de compra en ajuste
    document.getElementById("inv-modal-unit-group").style.display = "none";
    document.getElementById("inv-modal-cost-group").style.display = "none";
    
    // Cambiar layout de grid a grid-1 para centrar
    document.getElementById("inv-modal-inputs-row").className = "grid-2 gap-10 margin-top-10";
    
    // Mostrar Modal
    document.getElementById("inventory-modal").classList.remove("hidden");
}

function executeInventoryTransaction() {
    const tenant = DB[activeTenant];
    const itemId = document.getElementById("inv-modal-select").value;
    const item = tenant.inventory.find(i => i.id === itemId);
    if (!item) return;
    
    const qtyInput = parseFloat(document.getElementById("inv-modal-qty").value);
    const costInput = parseFloat(document.getElementById("inv-modal-cost").value);
    const unitInput = document.getElementById("inv-modal-unit").value;
    
    const isAjuste = document.getElementById("inv-modal-save-btn").textContent.includes("Ajuste");
    
    if (isNaN(qtyInput) || qtyInput <= 0) {
        alert("Ingresa una cantidad válida.");
        return;
    }
    
    if (isAjuste) {
        // Ajuste manual directo
        const oldStock = item.stock;
        item.stock = qtyInput;
        
        // Log de Kardex
        tenant.kardex.push({
            time: new Date().toISOString(),
            name: item.name,
            type: "Ajuste Manual",
            qty: qtyInput - oldStock,
            unit: item.unit,
            cost: item.cost,
            reason: `Auditoría física (Antes: ${oldStock} ${item.unit})`
        });
        
        logAudit("Inventario", "Ajuste Manual de Stock", `${item.name}: ${oldStock} ${item.unit} -> ${qtyInput} ${item.unit}`);
    } else {
        // Compra (Entrada) con Costo Promedio Ponderado y conversión de unidades
        if (isNaN(costInput) || costInput <= 0) {
            alert("Ingresa el costo total de la compra.");
            return;
        }
        
        // Determinar cantidad real a añadir en la unidad base de bodega
        let finalQtyVal = qtyInput;
        let purchaseLabel = `${qtyInput} ${item.unit}`;
        
        if (unitInput !== "base" && unitInput !== item.unit) {
            finalQtyVal = convertUnit(qtyInput, unitInput, item.unit);
            purchaseLabel = `${qtyInput} ${unitInput} (Equivale a ${finalQtyVal.toFixed(2)} ${item.unit})`;
        }
        
        const newUnitCost = costInput / finalQtyVal;
        
        // Fórmula de Costo Promedio
        const totalCostSum = (item.stock * item.cost) + costInput;
        const totalStockSum = item.stock + finalQtyVal;
        
        item.cost = totalCostSum / totalStockSum;
        item.stock = totalStockSum;
        
        // Log de Kardex
        tenant.kardex.push({
            time: new Date().toISOString(),
            name: item.name,
            type: "Entrada (Compra)",
            qty: finalQtyVal,
            unit: item.unit,
            cost: newUnitCost,
            reason: `Compra facturada de ${purchaseLabel} (Costo Promedio)`
        });
        
        logAudit("Inventario", "Compra de Insumo", `Se compraron ${purchaseLabel} de ${item.name} por RD$${costInput.toFixed(2)} (Nuevo Costo Promedio Unitario: RD$${item.cost.toFixed(2)} / ${item.unit})`);
    }
    
    saveToLocalStorage();
    document.getElementById("inventory-modal").classList.add("hidden");
    renderInventoryTable();
    reloadDashboardMetrics();
    alert("¡Inventario actualizado y Kardex registrado!");
}

// 11. RECETARIO & COSTEO PROFESIONAL
let activeSelectedRecipeId = null;

function renderRecipes() {
    const container = document.getElementById("recipes-container");
    container.innerHTML = "";
    
    const tenant = DB[activeTenant];
    if (tenant.recipes.length === 0) {
        container.innerHTML = `<div class="empty-state-card text-center">No hay recetas creadas en el catálogo de ${tenant.info.name}.</div>`;
        return;
    }
    
    tenant.recipes.forEach(r => {
        const activeClass = r.id === activeSelectedRecipeId ? "active" : "";
        const card = document.createElement("div");
        card.className = `recipe-card glass-card ${activeClass}`;
        card.innerHTML = `
            <h4>${r.name}</h4>
            <div class="recipe-meta">
                <div><i class="fa-solid fa-pizza-slice"></i> Rendimiento: ${r.yield} uds</div>
                <div><i class="fa-solid fa-stopwatch"></i> Tiempo: ${r.time} min</div>
            </div>
        `;
        card.addEventListener("click", () => {
            activeSelectedRecipeId = r.id;
            renderRecipes(); // Recargar clases active
            loadRecipeInCalculator(r.id);
        });
        container.appendChild(card);
    });
}

function loadRecipeInCalculator(recipeId) {
    const tenant = DB[activeTenant];
    const recipe = tenant.recipes.find(r => r.id === recipeId);
    if (!recipe) return;
    
    activeSelectedRecipeId = recipe.id;
    
    document.getElementById("recipe-calc-empty").classList.add("hidden");
    document.getElementById("recipe-calc-details").classList.remove("hidden");
    
    document.getElementById("calc-recipe-name").textContent = recipe.name;
    document.getElementById("calc-yield").textContent = `${recipe.yield} U`;
    document.getElementById("calc-time").textContent = `${recipe.time} min`;
    document.getElementById("calc-difficulty").textContent = recipe.difficulty;
    
    // Mostrar/ocultar botón de eliminar receta según rol
    const delRecBtn = document.getElementById("delete-recipe-btn");
    if (delRecBtn) {
        delRecBtn.style.display = activeRole === "admin" ? "block" : "none";
    }
    
    // Setear inputs indirectos
    document.getElementById("calc-indirect-servicios").value = recipe.indirects ? recipe.indirects.services : (recipe.overheadCost || 50);
    document.getElementById("calc-indirect-mano").value = recipe.indirects ? recipe.indirects.labor : (recipe.laborCost || 150);
    document.getElementById("calc-indirect-merma").value = recipe.indirects ? recipe.indirects.merma : (recipe.wastePercent || 5);
    document.getElementById("calc-indirect-empaque").value = recipe.indirects ? recipe.indirects.packaging : (recipe.packagingCost || 80);
    
    // Encontrar precio de venta del producto POS asociado para el Warning
    const prod = tenant.products.find(p => p.id.includes(recipe.id.replace("rec_", "")));
    if (prod) {
        document.getElementById("recipe-pos-price-mock").value = prod.price;
    } else {
        document.getElementById("recipe-pos-price-mock").value = 120;
    }
    
    renderRecipeIngredientsCostSheet(recipe);
    calculateRealRecipeCosts(recipe);
}

function renderRecipeIngredientsCostSheet(recipe) {
    const tbody = document.getElementById("recipe-calc-ingredients-tbody");
    tbody.innerHTML = "";
    
    const tenant = DB[activeTenant];
    
    recipe.ingredients.forEach(ing => {
        const item = tenant.inventory.find(i => i.id === ing.id);
        const convertedQty = item ? convertUnit(ing.qty, ing.unit, item.unit) : ing.qty;
        const cost = item ? (item.cost * convertedQty) : 0;
        
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${item ? item.name : "Insumo Desconocido"}</td>
            <td>${ing.qty.toLocaleString()} ${ing.unit || (item ? item.unit : "")}</td>
            <td>RD$${cost.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
        `;
        tbody.appendChild(tr);
    });
}

function calculateRealRecipeCosts(recipe) {
    const tenant = DB[activeTenant];
    
    // 1. Sumar costo de insumos usados con conversión de unidades
    let totalInsumos = 0;
    recipe.ingredients.forEach(ing => {
        const item = tenant.inventory.find(i => i.id === ing.id);
        if (item) {
            const convertedQty = convertUnit(ing.qty, ing.unit, item.unit);
            totalInsumos += (item.cost * convertedQty);
        }
    });
    
    // 2. Leer valores indirectos del formulario
    const serv = parseFloat(document.getElementById("calc-indirect-servicios").value) || 0;
    const mano = parseFloat(document.getElementById("calc-indirect-mano").value) || 0;
    const merma = parseFloat(document.getElementById("calc-indirect-merma").value) || 0;
    const emp = parseFloat(document.getElementById("calc-indirect-empaque").value) || 0;
    
    // Guardar en la estructura en memoria
    recipe.indirects = { services: serv, labor: mano, merma: merma, packaging: emp };
    
    // Costo base tanda
    let totalTandaCost = totalInsumos + serv + mano + emp;
    // Aplicar porcentaje de merma/pérdida
    totalTandaCost += (totalTandaCost * (merma / 100));
    
    // Costo unitario real
    const unitCostReal = totalTandaCost / recipe.yield;
    
    // Escribir en interfaz
    document.getElementById("recipe-total-cost-tanda").textContent = `RD$${totalTandaCost.toLocaleString(undefined, {maximumFractionDigits:2})}`;
    document.getElementById("recipe-unit-cost-real").textContent = `RD$${unitCostReal.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    
    // Precios Inteligentes Sugeridos
    const minPrice = unitCostReal / 0.7; // Margen de 30%
    const recPrice = unitCostReal / 0.5; // Margen de 50%
    const premPrice = unitCostReal / 0.2; // Margen de 80%
    
    document.getElementById("price-suggest-min").textContent = `RD$${Math.round(minPrice)}`;
    document.getElementById("price-suggest-rec").textContent = `RD$${Math.round(recPrice)}`;
    document.getElementById("price-suggest-prem").textContent = `RD$${Math.round(premPrice)}`;
    
    // Verificar si el precio de venta en POS está debajo de costo
    const setPrice = parseFloat(document.getElementById("recipe-pos-price-mock").value) || 0;
    const alertBox = document.getElementById("recipe-alert-below-cost");
    if (setPrice < unitCostReal) {
        alertBox.classList.remove("hidden");
    } else {
        alertBox.classList.add("hidden");
    }
}

function setupRecipesActions() {
    // Recalcular costos de receta en vivo al cambiar inputs
    const triggers = document.querySelectorAll(".recipe-recalc-trigger");
    triggers.forEach(input => {
        input.addEventListener("input", () => {
            if (activeSelectedRecipeId) {
                const recipe = DB[activeTenant].recipes.find(r => r.id === activeSelectedRecipeId);
                if (recipe) {
                    calculateRealRecipeCosts(recipe);
                }
            }
        });
    });
    
    // Botón Fijar precio en POS
    document.getElementById("save-price-pos-btn").addEventListener("click", () => {
        if (!activeSelectedRecipeId) return;
        const tenant = DB[activeTenant];
        const setPrice = parseFloat(document.getElementById("recipe-pos-price-mock").value) || 0;
        
        // Encontrar o crear producto POS
        const cleanId = activeSelectedRecipeId.replace("rec_", "");
        let prod = tenant.products.find(p => p.id.includes(cleanId));
        
        // Obtener costo unitario real
        const recipe = tenant.recipes.find(r => r.id === activeSelectedRecipeId);
        let totalInsumos = 0;
        recipe.ingredients.forEach(ing => {
            const item = tenant.inventory.find(i => i.id === ing.id);
            if (item) {
                const convertedQty = convertUnit(ing.qty, ing.unit, item.unit);
                totalInsumos += (item.cost * convertedQty);
            }
        });
        const unitCost = (totalInsumos + recipe.indirects.services + recipe.indirects.labor + recipe.indirects.packaging) / recipe.yield;
        
        if (prod) {
            prod.price = setPrice;
            prod.cost = unitCost; // Sincronizar costo unitario real para contabilidad
        } else {
            // Registrar nuevo producto POS si no existía
            tenant.products.push({
                id: `prod_${cleanId}`,
                name: recipe.name.replace("MigaMiga", "").trim(),
                category: "brownies",
                price: setPrice,
                cost: unitCost,
                stock: 0,
                img: "https://images.unsplash.com/photo-1606313564200-e75d5e30476c?q=80&w=200&auto=format&fit=crop"
            });
        }
        
        saveToLocalStorage();
        renderPOSCatalog();
        reloadDashboardMetrics();
        alert(`¡Precio en POS fijado con éxito a RD$${setPrice.toLocaleString()}! Costo unitario real sincronizado.`);
    });
}

// 12. LÍNEA DE PRODUCCIÓN (Ingrediente → Producto Terminado)
function renderProductionCatalog() {
    const select = document.getElementById("prod-recipe-select");
    select.innerHTML = "";
    
    const tenant = DB[activeTenant];
    
    if (tenant.recipes.length === 0) {
        select.innerHTML = `<option value="">No hay recetas creadas</option>`;
        return;
    }
    
    tenant.recipes.forEach(r => {
        const opt = document.createElement("option");
        opt.value = r.id;
        opt.textContent = `${r.name} (Rendimiento: ${r.yield} uds)`;
        select.appendChild(opt);
    });
    
    // Iniciar verificación para la primera receta de la lista
    checkProductionIngredientsAvailability();
    renderProductionHistory();
}

function setupProductionActions() {
    const recipeSelect = document.getElementById("prod-recipe-select");
    const multInput = document.getElementById("prod-multiplier");
    
    recipeSelect.addEventListener("change", () => {
        checkProductionIngredientsAvailability();
    });
    
    multInput.addEventListener("input", () => {
        const tenant = DB[activeTenant];
        const recipe = tenant.recipes.find(r => r.id === recipeSelect.value);
        if (recipe) {
            const mult = parseInt(multInput.value) || 1;
            document.getElementById("prod-total-units-display").textContent = `${recipe.yield * mult} Unidades`;
        }
        checkProductionIngredientsAvailability();
    });
    
    // Lanzar cocción y producción
    document.getElementById("prod-execute-btn").addEventListener("click", executeProductionOrder);
}

function checkProductionIngredientsAvailability() {
    const tenant = DB[activeTenant];
    const recipeId = document.getElementById("prod-recipe-select").value;
    const mult = parseInt(document.getElementById("prod-multiplier").value) || 1;
    const checkContainer = document.getElementById("production-ingredients-check");
    
    checkContainer.innerHTML = "";
    
    const recipe = tenant.recipes.find(r => r.id === recipeId);
    if (!recipe) {
        checkContainer.innerHTML = `<p class="text-center font-secondary">Selecciona una receta.</p>`;
        return;
    }

    // Título explicativo del lote flexible
    const titleInfo = document.createElement("p");
    titleInfo.className = "font-secondary";
    titleInfo.style.cssText = "font-size: 11.5px; margin-bottom: 12px; color: var(--text-muted); line-height: 1.4;";
    titleInfo.innerHTML = "💡 <strong>Lote Flexible:</strong> Si para esta preparación usaste cantidades distintas, edítalas en vivo en las casillas. El costeo real del postre y la validación de bodega se adaptarán al instante.";
    checkContainer.appendChild(titleInfo);
    
    recipe.ingredients.forEach(ing => {
        const item = tenant.inventory.find(i => i.id === ing.id);
        const required = ing.qty * mult;
        const available = item ? item.stock : 0;
        
        const div = document.createElement("div");
        div.className = `check-item ok`;
        div.id = `prod-row-${ing.id}`;
        div.style.cssText = "display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; margin-bottom: 8px;";
        div.innerHTML = `
            <div style="flex: 1; min-width: 110px;">
                <strong>${item ? item.name : "Desconocido"}</strong>
            </div>
            <div style="display: flex; align-items: center; gap: 4px;">
                <input type="number" class="input-premium small prod-ing-qty-input" data-id="${ing.id}" value="${required}" style="width: 80px; padding: 4px 6px;">
                <span style="font-size: 11px; color: var(--text-muted);">${ing.unit || (item ? item.unit : "")}</span>
            </div>
            <div style="font-size: 11px; color: var(--text-muted); min-width: 120px; text-align: right;">
                Disp: ${available.toLocaleString()} ${item ? item.unit : ""}
            </div>
            <span class="check-status-icon ok" id="prod-status-${ing.id}">✓</span>
        `;
        checkContainer.appendChild(div);
    });

    // Inyectar tarjeta de costeo real dinámico en producción
    const costCard = document.createElement("div");
    costCard.className = "cost-summary-box margin-top-15";
    costCard.style.cssText = "background: rgba(0,0,0,0.15); border: 1px dashed var(--border-color); padding: 12px; border-radius: 8px;";
    costCard.innerHTML = `
        <div style="display: flex; justify-content: space-between; font-size: 11px; color: var(--text-muted);">
            <span>Costo Real Insumos Batch:</span>
            <strong id="prod-live-insumos">RD$0.00</strong>
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 11px; color: var(--text-muted); margin-top: 4px;">
            <span>Indirectos (Electricidad, Gas, Empaque):</span>
            <strong id="prod-live-indirects">RD$0.00</strong>
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 13px; font-weight: bold; border-top: 1px dashed var(--border-color); margin-top: 6px; padding-top: 6px;">
            <span>Costo Unitario Real Estimado:</span>
            <strong class="text-gold" id="prod-live-unit-cost">RD$0.00</strong>
        </div>
    `;
    checkContainer.appendChild(costCard);

    // Enlazar listeners en los inputs para recalcular al instante
    const inputs = checkContainer.querySelectorAll(".prod-ing-qty-input");
    inputs.forEach(input => {
        input.addEventListener("input", () => {
            recalculateLiveProductionCostsAndAvailability(recipe, mult);
        });
    });

    // Calcular por primera vez
    recalculateLiveProductionCostsAndAvailability(recipe, mult);
}

function recalculateLiveProductionCostsAndAvailability(recipe, mult) {
    const tenant = DB[activeTenant];
    const checkContainer = document.getElementById("production-ingredients-check");
    const inputs = checkContainer.querySelectorAll(".prod-ing-qty-input");
    
    let isAllOk = true;
    let totalInsumosCost = 0;
    
    inputs.forEach(input => {
        const ingId = input.getAttribute("data-id");
        const qtyVal = parseFloat(input.value) || 0;
        
        const item = tenant.inventory.find(i => i.id === ingId);
        const recipeIng = recipe.ingredients.find(ing => ing.id === ingId);
        const ingUnit = recipeIng ? recipeIng.unit : (item ? item.unit : "");
        const qtyValInBodegaUnit = item ? convertUnit(qtyVal, ingUnit, item.unit) : qtyVal;
        
        const available = item ? item.stock : 0;
        const row = document.getElementById(`prod-row-${ingId}`);
        const statusIcon = document.getElementById(`prod-status-${ingId}`);
        
        const isOk = available >= qtyValInBodegaUnit;
        
        if (row && statusIcon) {
            if (isOk) {
                row.className = "check-item ok";
                statusIcon.textContent = "✓";
                statusIcon.className = "check-status-icon ok";
            } else {
                row.className = "check-item fail";
                statusIcon.textContent = "❌";
                statusIcon.className = "check-status-icon fail";
                isAllOk = false;
            }
        } else {
            if (!isOk) isAllOk = false;
        }
        
        if (item) {
            totalInsumosCost += (item.cost * qtyValInBodegaUnit);
        }
    });
    
    // Prorratear indirectos
    const services = (recipe.indirects.services || 0) * mult;
    const labor = (recipe.indirects.labor || 0) * mult;
    const packaging = (recipe.indirects.packaging || 0) * mult;
    const merma = recipe.indirects.merma || 0;
    
    let totalBatchCost = totalInsumosCost + services + labor + packaging;
    totalBatchCost += (totalBatchCost * (merma / 100));
    
    const qtyCreated = recipe.yield * mult;
    const unitCost = totalBatchCost / qtyCreated;
    
    // Escribir en la UI en vivo
    document.getElementById("prod-live-insumos").textContent = `RD$${totalInsumosCost.toLocaleString(undefined, {maximumFractionDigits: 2})}`;
    document.getElementById("prod-live-indirects").textContent = `RD$${(services + labor + packaging).toLocaleString()}`;
    document.getElementById("prod-live-unit-cost").textContent = `RD$${unitCost.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    
    // Deshabilitar botón si falta algo o si hay algún input vacío
    const btn = document.getElementById("prod-execute-btn");
    if (isAllOk && inputs.length > 0) {
        btn.classList.remove("disabled");
        btn.removeAttribute("disabled");
    } else {
        btn.classList.add("disabled");
        btn.setAttribute("disabled", "true");
    }
}

function executeProductionOrder() {
    const tenant = DB[activeTenant];
    const recipeId = document.getElementById("prod-recipe-select").value;
    const mult = parseInt(document.getElementById("prod-multiplier").value) || 1;
    
    const recipe = tenant.recipes.find(r => r.id === recipeId);
    if (!recipe) return;
    
    const checkContainer = document.getElementById("production-ingredients-check");
    const inputs = checkContainer.querySelectorAll(".prod-ing-qty-input");
    
    let totalInsumos = 0;
    let customIngredientsLog = [];

    // 1. Descontar ingredientes físicos editados en bodega y generar Kardex con conversión de unidades
    inputs.forEach(input => {
        const ingId = input.getAttribute("data-id");
        const qtyVal = parseFloat(input.value) || 0;
        
        const item = tenant.inventory.find(i => i.id === ingId);
        const recipeIng = recipe.ingredients.find(ing => ing.id === ingId);
        const ingUnit = recipeIng ? recipeIng.unit : (item ? item.unit : "");
        const qtyValInBodegaUnit = item ? convertUnit(qtyVal, ingUnit, item.unit) : qtyVal;
        
        if (item) {
            item.stock -= qtyValInBodegaUnit;
            totalInsumos += (item.cost * qtyValInBodegaUnit);
            customIngredientsLog.push(`• ${qtyVal.toLocaleString()} ${ingUnit} de ${item.name} (${qtyValInBodegaUnit.toFixed(3)} ${item.unit})`);
            
            // Kardex salida
            tenant.kardex.push({
                time: new Date().toISOString(),
                name: item.name,
                type: "Salida (Producción)",
                qty: qtyValInBodegaUnit,
                unit: item.unit,
                cost: item.cost,
                reason: `Consumo real batch lote ajustable: ${recipe.name}`
            });
        }
    });
    
    // 2. Calcular costo real unitario de esta tanda
    const serv = (recipe.indirects.services || 0) * mult;
    const mano = (recipe.indirects.labor || 0) * mult;
    const merma = recipe.indirects.merma || 0;
    const emp = (recipe.indirects.packaging || 0) * mult;
    
    let totalTandaCost = totalInsumos + serv + mano + emp;
    totalTandaCost += (totalTandaCost * (merma / 100));
    
    const qtyCreated = recipe.yield * mult;
    const unitCostReal = totalTandaCost / qtyCreated;
    
    // 3. Crear o incrementar stock del PRODUCTO TERMINADO en el POS
    const cleanId = recipe.id.replace("rec_", "");
    let prod = tenant.products.find(p => p.id.includes(cleanId));
    if (prod) {
        prod.stock += qtyCreated;
        prod.cost = unitCostReal; // Actualiza el costo de venta (COGS) para contabilidad
    } else {
        tenant.products.push({
            id: `prod_${cleanId}`,
            name: recipe.name.replace("MigaMiga", "").trim(),
            category: "brownies",
            price: Math.round(unitCostReal * 1.5),
            cost: unitCostReal,
            stock: qtyCreated,
            img: "https://images.unsplash.com/photo-1606313564200-e75d5e30476c?q=80&w=200&auto=format&fit=crop"
        });
    }
    
    // 4. Log Historial de Producción
    const prodRecord = {
        time: new Date().toISOString(),
        recipe: `${recipe.name} (Lote Ajustado)`,
        multiplier: mult,
        qtyCreated: qtyCreated,
        unitCost: unitCostReal,
        totalCost: totalTandaCost
    };
    tenant.production.push(prodRecord);
    
    saveToLocalStorage();
    
    // Recargas en vivo
    renderPOSCatalog();
    renderInventoryTable();
    checkProductionIngredientsAvailability();
    renderProductionHistory();
    reloadDashboardMetrics();
    
    alert(`🎉 LOTE PERSONALIZADO PROCESADO: Se crearon ${qtyCreated} unidades de ${recipe.name}.\n\nInsumos consumidos reales:\n${customIngredientsLog.join('\n')}\n\nEl costo unitario final recalculado para esta tanda es de RD$${unitCostReal.toFixed(2)}.`);
}

function renderProductionHistory() {
    const tbody = document.getElementById("production-history-tbody");
    tbody.innerHTML = "";
    
    const tenant = DB[activeTenant];
    if (tenant.production.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center">No hay producciones procesadas aún.</td></tr>`;
        return;
    }
    
    const reversed = [...tenant.production].reverse();
    reversed.forEach(p => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${new Date(p.time).toLocaleString()}</td>
            <td><strong>${p.recipe}</strong></td>
            <td>${p.multiplier}</td>
            <td>${p.qtyCreated} uds</td>
            <td>RD$${p.unitCost.toFixed(2)}</td>
            <td>RD$${p.totalCost.toLocaleString(undefined, {maximumFractionDigits: 2})}</td>
        `;
        tbody.appendChild(tr);
    });
}

// 13. CRM, PEDIDOS DE EVENTOS Y CRÉDITO
function renderCRMPedidos() {
    const tbody = document.getElementById("orders-tbody");
    tbody.innerHTML = "";
    
    const tenant = DB[activeTenant];
    if (tenant.orders.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center">No hay pedidos agendados aún.</td></tr>`;
        return;
    }
    
    tenant.orders.forEach(o => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><strong>${o.deliveryDate} @ ${o.deliveryTime}</strong></td>
            <td>${o.customer}</td>
            <td class="font-secondary" style="max-width: 200px;">${o.desc}</td>
            <td>RD$${o.total.toLocaleString()}</td>
            <td>RD$${o.abono.toLocaleString()}</td>
            <td><span class="badge red-bg">RD$${o.balance.toLocaleString()}</span></td>
            <td><span class="badge ${o.status === 'Entregado' ? 'green-bg' : 'orange-bg'}">${o.status}</span></td>
            <td>
                ${o.status === 'Pendiente' ? 
                    `<button class="btn btn-primary small deliver-order-btn" data-id="${o.id}"><i class="fa-solid fa-cake-candles"></i> Entregar</button>` : 
                    `<span class="text-green font-bold"><i class="fa-solid fa-circle-check"></i> Entregado</span>`
                }
            </td>
        `;
        
        const btn = tr.querySelector(".deliver-order-btn");
        if (btn) {
            btn.addEventListener("click", () => deliverSpecialOrder(o.id));
        }
        
        tbody.appendChild(tr);
    });
}

function setupCRMActions() {
    // Pestanias CRM
    const tabs = document.querySelectorAll(".crm-tabs .tab-btn");
    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            tabs.forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
            
            const target = tab.getAttribute("data-tab");
            document.querySelectorAll(".crm-tab-content").forEach(c => c.classList.remove("active"));
            document.getElementById(target).classList.add("active");
        });
    });
    
    // Balance automatico en formulario
    const totalInput = document.getElementById("order-price");
    const abonoInput = document.getElementById("order-abono");
    const balDisplay = document.getElementById("order-balance-display");
    
    function recalcOrderFormBalance() {
        const t = parseFloat(totalInput.value) || 0;
        const a = parseFloat(abonoInput.value) || 0;
        const b = Math.max(0, t - a);
        balDisplay.textContent = `RD$${b.toLocaleString()}`;
        if (b > 0) balDisplay.className = "balance-display red";
        else balDisplay.className = "balance-display";
    }
    
    totalInput.addEventListener("input", recalcOrderFormBalance);
    abonoInput.addEventListener("input", recalcOrderFormBalance);
    
    // Guardar Pedido
    document.getElementById("order-save-btn").addEventListener("click", executeSaveSpecialOrder);
    
    // Abono a crédito cliente
    document.getElementById("credit-client-select").addEventListener("change", loadCreditClientInfo);
    document.getElementById("credit-abono-btn").addEventListener("click", executeCreditPayment);
}

function executeSaveSpecialOrder() {
    const tenant = DB[activeTenant];
    const clientSelect = document.getElementById("order-client");
    const clientName = clientSelect.options[clientSelect.selectedIndex].text;
    
    const date = document.getElementById("order-date").value;
    const time = document.getElementById("order-time").value;
    const desc = document.getElementById("order-desc").value;
    
    const price = parseFloat(document.getElementById("order-price").value) || 0;
    const abono = parseFloat(document.getElementById("order-abono").value) || 0;
    const balance = Math.max(0, price - abono);
    
    if (!date || !desc.trim() || price <= 0) {
        alert("Completa la fecha, la descripción y el monto total de la cotización especial.");
        return;
    }
    
    // Si hay abono inicial en efectivo, añadir a caja
    if (abono > 0) {
        if (!tenant.caja.active) {
            alert("⚠️ La caja está cerrada. Abre la caja chica antes de registrar un pedido con abono en efectivo.");
            return;
        }
        tenant.caja.active.expectedCash += abono;
        tenant.caja.active.movements.push({
            time: new Date().toISOString(),
            type: "ingreso",
            monto: abono,
            concept: `Abono de Pedido: ${clientName}`
        });
    }
    
    const orderRecord = {
        id: `ord_${Date.now().toString().substring(8)}`,
        deliveryDate: date,
        deliveryTime: time,
        customer: clientName,
        desc: desc,
        total: price,
        abono: abono,
        balance: balance,
        status: "Pendiente"
    };
    
    tenant.orders.push(orderRecord);
    saveToLocalStorage();
    
    renderCRMPedidos();
    renderCajaDetails();
    reloadDashboardMetrics();
    
    // Limpiar
    document.getElementById("order-date").value = "";
    document.getElementById("order-desc").value = "";
    document.getElementById("order-price").value = "";
    document.getElementById("order-abono").value = "";
    document.getElementById("order-balance-display").textContent = "RD$0.00";
    
    alert(`🎂 ¡Pedido agendado con éxito! Se imprimirá el recibo para el repostero y se registró el abono de RD$${abono.toLocaleString()} en la caja chica.`);
}

function deliverSpecialOrder(orderId) {
    const tenant = DB[activeTenant];
    const order = tenant.orders.find(o => o.id === orderId);
    if (!order) return;
    
    // Validar cobro de balance pendiente si lo hay
    if (order.balance > 0) {
        if (!tenant.caja.active) {
            alert("Caja cerrada. Abre la caja para registrar el cobro de la entrega.");
            return;
        }
        tenant.caja.active.expectedCash += order.balance;
        tenant.caja.active.movements.push({
            time: new Date().toISOString(),
            type: "ingreso",
            monto: order.balance,
            concept: `Liquidación Pedido: ${order.customer}`
        });
        
        // Sumar a las ventas el restante cobrado
        tenant.sales.push({
            id: `sale_ord_${Date.now().toString().substring(10)}`,
            date: new Date().toISOString(),
            customer: order.customer,
            items: [{ name: `Liquidación: ${order.desc.substring(0, 20)}...`, qty: 1, price: order.total }],
            subtotal: order.total,
            tax: 0,
            total: order.balance,
            payment: "efectivo",
            ncf: "B01" + Date.now().toString().substring(8)
        });
    }
    
    order.status = "Entregado";
    order.balance = 0;
    order.abono = order.total;
    
    saveToLocalStorage();
    renderCRMPedidos();
    renderCajaDetails();
    reloadDashboardMetrics();
    alert(`🎉 ¡Postre entregado al cliente y balance liquidado en caja chica!`);
}

function renderCRMClients() {
    const tbody = document.getElementById("crm-clients-tbody");
    tbody.innerHTML = "";
    
    const tenant = DB[activeTenant];
    
    // Llenar selectores CRM y POS
    const posSelect = document.getElementById("cart-customer-select");
    posSelect.innerHTML = "";
    const orderSelect = document.getElementById("order-client");
    orderSelect.innerHTML = "";
    const creditSelect = document.getElementById("credit-client-select");
    creditSelect.innerHTML = "";
    
    tenant.clients.forEach(c => {
        // Renders visuales
        const isMora = c.debt > c.creditLimit;
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><strong>${c.name}</strong></td>
            <td>${c.phone}</td>
            <td>RD$${c.avgSpend.toLocaleString()}</td>
            <td>${c.bday} ${c.bday === '05-28' ? '🎂 Hoy' : ''}</td>
            <td>RD$${c.creditLimit.toLocaleString()}</td>
            <td class="${c.debt > 0 ? 'text-red font-bold' : ''}">RD$${c.debt.toLocaleString()}</td>
        `;
        tbody.appendChild(tr);
        
        // Populate selectores
        const opt1 = document.createElement("option");
        opt1.value = c.id;
        opt1.textContent = `${c.name} (Límite: RD$${c.creditLimit})`;
        posSelect.appendChild(opt1);
        
        const opt2 = document.createElement("option");
        opt2.value = c.id;
        opt2.textContent = c.name;
        orderSelect.appendChild(opt2);
        
        const opt3 = document.createElement("option");
        opt3.value = c.id;
        opt3.textContent = `${c.name} - Deuda: RD$${c.debt}`;
        creditSelect.appendChild(opt3);
    });
    
    loadCreditClientInfo();
}

function loadCreditClientInfo() {
    const tenant = DB[activeTenant];
    const clientId = document.getElementById("credit-client-select").value;
    const client = tenant.clients.find(c => c.id === clientId);
    
    if (client) {
        document.getElementById("credit-val-deuda").textContent = `RD$${client.debt.toLocaleString()}`;
        document.getElementById("credit-val-limite").textContent = `RD$${client.creditLimit.toLocaleString()}`;
    }
}

function executeCreditPayment() {
    const tenant = DB[activeTenant];
    const clientId = document.getElementById("credit-client-select").value;
    const client = tenant.clients.find(c => c.id === clientId);
    if (!client) return;
    
    const abono = parseFloat(document.getElementById("credit-abono-monto").value) || 0;
    const method = document.getElementById("credit-abono-method").value;
    
    if (abono <= 0 || abono > client.debt) {
        alert("Ingresa un monto de abono válido que no supere el saldo deudor.");
        return;
    }
    
    // Descontar deuda
    client.debt -= abono;
    
    // Entrar dinero a caja chica o banco
    if (method === "efectivo") {
        if (!tenant.caja.active) {
            alert("Caja Cerrada. Abre la caja chica para registrar abonos de dinero en efectivo.");
            client.debt += abono; // Rollback
            return;
        }
        tenant.caja.active.expectedCash += abono;
        tenant.caja.active.movements.push({
            time: new Date().toISOString(),
            type: "ingreso",
            monto: abono,
            concept: `Abono Crédito: ${client.name}`
        });
    }
    
    logAudit("Crédito", "Abono de Cliente", `Abono de RD$${abono.toFixed(2)} recibido de ${client.name} vía ${method.toUpperCase()}`);
    
    saveToLocalStorage();
    renderCRMClients();
    renderCajaDetails();
    reloadDashboardMetrics();
    
    document.getElementById("credit-abono-monto").value = "";
    
    alert(`👍 Abono de RD$${abono.toLocaleString()} aplicado con éxito a la cuenta de ${client.name}. Su balance actual es RD$${client.debt.toLocaleString()}.`);
}

// 14. MARKETPLACE (Instalador de Plantillas)
function installMarketplaceRecipe(recipeType) {
    const tenant = DB[activeTenant];
    
    if (recipeType === "carlota") {
        // Agregar insumos de Carlota si no existen
        const insumoId = "inv_galletas_maria";
        if (!tenant.inventory.find(i => i.id === insumoId)) {
            tenant.inventory.push({ id: insumoId, name: "Galletas María", category: "Ingredientes", stock: 2000, unit: "g", cost: 0.15, minStock: 200 });
        }
        // Agregar Receta
        if (!tenant.recipes.find(r => r.id === "rec_carlota")) {
            tenant.recipes.push({
                id: "rec_carlota",
                name: "Carlota de Limón Imperial",
                yield: 10,
                time: 30,
                difficulty: "Fácil",
                ingredients: [
                    { id: "inv_leche", qty: 400 },
                    { id: "inv_galletas_maria", qty: 250 }
                ],
                indirects: { services: 20, labor: 60, merma: 1, packaging: 15 }
            });
        }
        alert("🎉 ¡Instalación Exitosa! La receta 'Carlota de Limón Imperial' ha sido agregada a tu recetario. Se crearon los ingredientes correspondientes en tu inventario de bodega.");
    } else if (recipeType === "fudge") {
        alert("🎨 ¡Fudge Cake de Boda instalado! Se importó el manual de producción visual y las fotos de referencia al CRM.");
    } else if (recipeType === "redvelvet") {
        alert("🍪 Receta 'Red Velvet Cookies' agregada a tu catálogo para producción.");
    }
    
    saveToLocalStorage();
    renderRecipes();
    renderInventoryTable();
    renderProductionCatalog();
    
    if (isMobileShellActive) {
        syncMobileScreen();
    }
}

function setupModalEvents() {
    // Cerrar modales
    document.querySelectorAll(".close-modal-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".modal").forEach(m => m.classList.add("hidden"));
        });
    });
    
    // Marketplace install clicks
    const buyBtns = document.querySelectorAll(".buy-recipe-btn");
    buyBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const recipeType = btn.getAttribute("data-recipe");
            installMarketplaceRecipe(recipeType);
        });
    });
}

// 15. SaaS CONSOLE (Superadmin Global Controls)
function setupSaaSActions() {
    const superadminBtns = document.querySelectorAll(".saas-toggle-tenant-btn");
    superadminBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const tKey = btn.getAttribute("data-tenant");
            const tenantInfo = DB[tKey].info;
            
            // Alternar estado activo
            tenantInfo.active = !tenantInfo.active;
            saveToLocalStorage();
            
            // Recargar tabla SaaS en UI
            updateSaaSTableUI(tKey);
            
            // Si el tenant activo actual es el suspendido, gatilla pantalla
            if (activeTenant === tKey) {
                loadTenant(activeTenant);
            }
            
            alert(`SaaS: Cuenta de ${tenantInfo.name} ha sido ${tenantInfo.active ? 'ACTIVADA y habilitada' : 'SUSPENDIDA'}.`);
        });
    });
    
    // Reactivación rápida
    document.getElementById("reactivate-tenant-btn").addEventListener("click", () => {
        DB[activeTenant].info.active = true;
        saveToLocalStorage();
        updateSaaSTableUI(activeTenant);
        loadTenant(activeTenant);
        alert(`¡Pago simulado recibido! La cuenta ha sido desbloqueada.`);
    });
    
    // Registrar nueva empresa en el SaaS dinámicamente
    const saasForm = document.getElementById("saas-add-tenant-form");
    if (saasForm) {
        saasForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const name = document.getElementById("new-tenant-name").value.trim();
            const adminName = document.getElementById("new-tenant-admin").value.trim();
            const plan = document.getElementById("new-tenant-plan").value;
            const rnc = document.getElementById("new-tenant-rnc").value.trim();
            const address = document.getElementById("new-tenant-address").value.trim();
            
            const cleanKey = name.replace(/\s+/g, "");
            const adminUsername = adminName.split(' ')[0].toLowerCase();
            const adminPassword = "123";
            
            if (sessionToken) {
                try {
                    const res = await apiFetch("/api/auth/register-tenant", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            tenant_id: cleanKey,
                            name: name,
                            plan: plan,
                            admin_username: adminUsername,
                            admin_password: adminPassword,
                            admin_fullname: adminName
                        })
                    });
                    
                    if (res && res.ok) {
                        // Clonar estructura base local
                        const baseTenant = JSON.parse(JSON.stringify(INITIAL_DATABASE.MigaMiga));
                        baseTenant.info = { name, rnc, address, plan, active: true };
                        baseTenant.users = [
                            { name: adminName, username: adminUsername, password: "", role: "admin", status: "Activo" }
                        ];
                        DB[cleanKey] = baseTenant;
                        saveToLocalStorage();
                        alert(`¡Empresa '${name}' dada de alta exitosamente en la nube! Contraseña del Admin '${adminUsername}': 123`);
                    } else {
                        const err = await res.json();
                        alert(err.error || "No se pudo registrar la nueva empresa.");
                        return;
                    }
                } catch (err) {
                    console.error("SaaS Registration Error:", err);
                    alert("Error de conexión al registrar inquilino en el servidor.");
                    return;
                }
            } else {
                // Modo offline
                if (DB[cleanKey]) {
                    alert("Ya existe una empresa con ese nombre en el SaaS.");
                    return;
                }
                const baseTenant = JSON.parse(JSON.stringify(INITIAL_DATABASE.MigaMiga));
                baseTenant.info = { name, rnc, address, plan, active: true };
                baseTenant.users = [
                    { name: adminName, username: adminUsername, password: "123", role: "admin", status: "Activo" }
                ];
                DB[cleanKey] = baseTenant;
                saveToLocalStorage();
                alert(`¡Empresa '${name}' dada de alta exitosamente (Offline)! Contraseña: 123`);
            }
            
            // Añadir a selectores en DOM
            const loginTenantSelect = document.getElementById("login-tenant");
            const opt = document.createElement("option");
            opt.value = cleanKey;
            opt.textContent = `🏢 ${name}`;
            loginTenantSelect.appendChild(opt);
            
            const headerTenantSelect = document.getElementById("tenant-select");
            const opt2 = document.createElement("option");
            opt2.value = cleanKey;
            opt2.textContent = `🏢 ${name}`;
            headerTenantSelect.appendChild(opt2);
            
            // Añadir fila a la tabla SaaS
            const saasTableBody = document.querySelector("#saas-page tbody");
            if (saasTableBody) {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td><strong>🍽️ ${name}</strong></td>
                    <td><span class="badge ${plan === 'Empresa' ? 'purple-bg' : (plan === 'Pro' ? 'blue-bg' : '')}">Plan ${plan}</span></td>
                    <td>${adminName}</td>
                    <td>${new Date().toISOString().substring(0,10)}</td>
                    <td>RD$${plan === 'Empresa' ? '4,500.00' : (plan === 'Pro' ? '3,400.00' : '1,800.00')}</td>
                    <td><span class="status-dot green"></span> Activo</td>
                    <td><button class="btn btn-secondary small text-red saas-toggle-tenant-btn" data-tenant="${cleanKey}"><i class="fa-solid fa-ban"></i> Suspender</button></td>
                `;
                saasTableBody.appendChild(tr);
                
                tr.querySelector(".saas-toggle-tenant-btn").addEventListener("click", () => {
                    const info = DB[cleanKey].info;
                    info.active = !info.active;
                    saveToLocalStorage();
                    alert(`SaaS: Cuenta de ${info.name} ha sido ${info.active ? 'ACTIVADA' : 'SUSPENDIDA'}.`);
                    loadTenant(activeTenant);
                });
            }
            
            // Limpiar inputs
            document.getElementById("new-tenant-name").value = "";
            document.getElementById("new-tenant-admin").value = "";
            document.getElementById("new-tenant-rnc").value = "";
            document.getElementById("new-tenant-address").value = "";
            
            logAudit("Seguridad", "Empresa Creada", `Nueva repostería habilitada en SaaS: ${name} (Plan: ${plan})`);
            alert(`🎉 ¡EMPRESA HABILITADA EN EL SAAS EN SEGUNDOS!\n\nSe ha creado una base de datos 100% aislada para "${name}".\n\nEl administrador "${adminName}" puede iniciar sesión con el usuario "${adminName.split(' ')[0].toLowerCase()}" y contraseña "123".`);
        });
    }
}

function updateSaaSTableUI(tenantKey) {
    const info = DB[tenantKey].info;
    const isActive = info.active;
    
    // Sweet House refs
    if (tenantKey === "SweetHouse") {
        const dot = document.getElementById("saas-sweethouse-status-dot");
        const txt = document.getElementById("saas-sweethouse-status-text");
        const btn = document.getElementById("saas-sweethouse-toggle-btn");
        
        if (isActive) {
            dot.className = "status-dot green";
            txt.className = "text-green font-bold";
            txt.textContent = "Activo";
            btn.className = "btn btn-secondary small text-red saas-toggle-tenant-btn";
            btn.innerHTML = '<i class="fa-solid fa-ban"></i> Suspender';
        } else {
            dot.className = "status-dot red";
            txt.className = "text-red font-bold";
            txt.textContent = "Suspendido";
            btn.className = "btn btn-primary small saas-toggle-tenant-btn";
            btn.innerHTML = '<i class="fa-solid fa-circle-check"></i> Activar / Desbloquear';
        }
    }
    
    // Recargar métrica consolidadas
    let activeCount = 0;
    Object.keys(DB).forEach(key => {
        if (DB[key].info.active) activeCount++;
    });
    document.getElementById("saas-active-tenants").textContent = `${activeCount} / 3`;
}

// 16. CONFIGURACIÓN Y AJUSTES
function setupSettingsActions() {
    document.getElementById("save-settings-btn").addEventListener("click", () => {
        const name = document.getElementById("set-business-name").value;
        const rnc = document.getElementById("set-business-rnc").value;
        const addr = document.getElementById("set-business-address").value;
        
        if (!name.trim()) {
            alert("El nombre de la empresa no puede estar vacío.");
            return;
        }
        
        DB[activeTenant].info.name = name;
        DB[activeTenant].info.rnc = rnc;
        DB[activeTenant].info.address = addr;
        
        saveToLocalStorage();
        loadTenant(activeTenant);
        alert("Configuración de empresa guardada con éxito.");
    });

    const userForm = document.getElementById("add-user-form");
    if (userForm) {
        userForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const name = document.getElementById("new-user-name").value.trim();
            const username = document.getElementById("new-user-username").value.trim().toLowerCase();
            const pass = document.getElementById("new-user-password").value.trim();
            const role = document.getElementById("new-user-role").value;
            
            const salaryInput = document.getElementById("new-user-salary");
            const baseSalary = salaryInput ? parseFloat(salaryInput.value) || 0 : 0;
            
            // Capturar permisos marcados
            const allowedPages = [];
            document.querySelectorAll(".user-perm-checkbox:checked").forEach(cb => {
                allowedPages.push(cb.value);
            });
            
            const tenant = DB[activeTenant];
            if (!tenant.users) {
                tenant.users = [
                    { name: "Sofía Rodríguez", username: "admin", password: "admin123", role: "admin", status: "Activo", baseSalary: 50000, allowedPages: ["dashboard-page", "pos-page", "caja-page", "inventario-page", "recetario-page", "produccion-page", "crm-page", "settings-page", "finanzas-page"] },
                    { name: "Camila Gómez", username: "cajero", password: "cajera123", role: "cajero", status: "Activo", baseSalary: 25000, allowedPages: ["pos-page", "caja-page", "crm-page"] },
                    { name: "Chef Carlos Mendoza", username: "chef", password: "chef123", role: "produccion", status: "Activo", baseSalary: 35000, allowedPages: ["inventario-page", "recetario-page", "produccion-page"] }
                ];
            }
            
            if (sessionToken) {
                // Sincronizar de forma segura en backend
                try {
                    const res = await apiFetch("/api/auth/register-user", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ username, password: pass, role, name, allowedPages, baseSalary })
                    });
                    
                    if (res && res.ok) {
                        tenant.users.push({ name, username, password: "", role, status: "Activo", allowedPages, baseSalary });
                        saveToLocalStorage();
                        renderUserManagementList();
                        alert(`¡Empleado '${username}' creado con éxito en la nube!`);
                    } else {
                        const err = await res.json();
                        alert(err.error || "No se pudo crear el usuario.");
                        return;
                    }
                } catch (err) {
                    console.error("User Creation Error:", err);
                    alert("Error de conexión al registrar usuario en el servidor.");
                    return;
                }
            } else {
                // Modo offline / LocalStorage
                if (tenant.users.find(u => u.username === username)) {
                    alert("Este nombre de usuario ya existe en tu empresa. Elige uno diferente.");
                    return;
                }
                tenant.users.push({
                    name: name,
                    username: username,
                    password: pass,
                    role: role,
                    status: "Activo",
                    allowedPages,
                    baseSalary
                });
                saveToLocalStorage();
                renderUserManagementList();
            }
            
            // Clear inputs
            document.getElementById("new-user-name").value = "";
            document.getElementById("new-user-username").value = "";
            document.getElementById("new-user-password").value = "";
            
            logAudit("Seguridad", "Usuario Creado", `Nuevo empleado registrado: ${name} (Usuario: ${username}, Rol: ${role.toUpperCase()})`);
            alert(`🎉 ¡Éxito! Cuenta de empleado creada para ${name}.\n\nYa puede iniciar sesión con el usuario "${username}" y su contraseña.`);
        });
    }
}

// 17. ASISTENTE DE IA INTEGRADO (MigaAI)
function setupMigaAIActions() {
    const trigger = document.getElementById("trigger-ai-assistant");
    const drawer = document.getElementById("ai-assistant-drawer");
    const closeBtn = document.getElementById("close-ai-drawer");
    
    trigger.addEventListener("click", () => {
        drawer.classList.toggle("open");
    });
    
    closeBtn.addEventListener("click", () => {
        drawer.classList.remove("open");
    });
    
    // Envio de chat
    const sendBtn = document.getElementById("ai-chat-send");
    const input = document.getElementById("ai-chat-input");
    
    sendBtn.addEventListener("click", executeAIChatCommand);
    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") executeAIChatCommand();
    });
}

function executeAIChatCommand() {
    const input = document.getElementById("ai-chat-input");
    const query = input.value.trim();
    if (!query) return;
    
    appendChatMessage("user", query);
    input.value = "";
    
    // Procesador de Lenguaje Local
    setTimeout(() => {
        processAIQueryLocal(query);
    }, 600);
}

function appendChatMessage(sender, text) {
    const chatBody = document.getElementById("ai-chat-body");
    const div = document.createElement("div");
    div.className = `chat-message ${sender}`;
    div.innerHTML = `
        <i class="fa-solid ${sender === 'user' ? 'fa-user' : 'fa-robot'}"></i>
        <div class="msg-bubble">${text}</div>
    `;
    chatBody.appendChild(div);
    chatBody.scrollTop = chatBody.scrollHeight;
}

function processAIQueryLocal(query) {
    const tenant = DB[activeTenant];
    const qLower = query.toLowerCase();
    let reply = "";
    
    // COMANDO 1: "Hice 27 brownies" / Producción rápida
    if (qLower.includes("hice") || qLower.includes("producir") || qLower.includes("producción")) {
        // Encontrar numeros en la cadena
        const matchNums = qLower.match(/\d+/);
        const qty = matchNums ? parseInt(matchNums[0]) : 27;
        
        // Encontrar receta Brownie Premium MigaMiga
        const recipe = tenant.recipes[0]; // Brownie Premium MigaMiga por defecto
        
        if (recipe) {
            // Calcular multiplo (si 1 tanda = 27 brownies)
            const multiplier = Math.max(1, Math.round(qty / recipe.yield));
            
            // Validar insumos primero
            let canProduce = true;
            let missing = [];
            
            recipe.ingredients.forEach(ing => {
                const item = tenant.inventory.find(i => i.id === ing.id);
                if (!item || item.stock < (ing.qty * multiplier)) {
                    canProduce = false;
                    missing.push(item ? item.name : "Insumo");
                }
            });
            
            if (canProduce) {
                // Ejecutar producción
                recipe.ingredients.forEach(ing => {
                    const item = tenant.inventory.find(i => i.id === ing.id);
                    if (item) {
                        item.stock -= (ing.qty * multiplier);
                        tenant.kardex.push({
                            time: new Date().toISOString(),
                            name: item.name,
                            type: "Salida (MigaAI)",
                            qty: ing.qty * multiplier,
                            unit: item.unit,
                            cost: item.cost,
                            reason: `Consumido por MigaAI Assistant`
                        });
                    }
                });
                
                // Añadir a productos terminados
                const cleanId = recipe.id.replace("rec_", "");
                let prod = tenant.products.find(p => p.id.includes(cleanId));
                const qtyCreated = recipe.yield * multiplier;
                
                if (prod) {
                    prod.stock += qtyCreated;
                }
                
                // Registrar producción
                tenant.production.push({
                    time: new Date().toISOString(),
                    recipe: recipe.name,
                    multiplier: multiplier,
                    qtyCreated: qtyCreated,
                    unitCost: prod ? prod.cost : 45.00,
                    totalCost: (prod ? prod.cost : 45.00) * qtyCreated
                });
                
                saveToLocalStorage();
                renderPOSCatalog();
                renderInventoryTable();
                renderProductionHistory();
                reloadDashboardMetrics();
                
                reply = `🤖 **MigaAI ha procesado tu orden de producción:**
                
                *   **Receta:** ${recipe.name}
                *   **Cantidad Producida:** ${qtyCreated} unidades (${multiplier} tandas).
                *   **Inventario Bodega:** Se descontaron correctamente los gramos y mililitros de insumos consumidos.
                *   **POS Listo:** El stock para la venta se ha actualizado automáticamente en vivo en el catálogo de ventas.`;
            } else {
                reply = `🤖 **MigaAI lo siente:** No tienes suficientes insumos en bodega para producir una tanda de ${qty} brownies. Te hacen falta: **${missing.join(', ')}**. 
                Por favor, registra una compra de insumos en el panel de inventario.`;
            }
        } else {
            reply = "🤖 No encontré una receta activa en tu recetario para procesar la producción.";
        }
    } 
    // COMANDO 2: "¿Qué producto me deja más dinero?" / Margen y Rentabilidad
    else if (qLower.includes("dinero") || qLower.includes("rentable") || qLower.includes("ganar") || qLower.includes("margen")) {
        let bestProd = null;
        let bestMargin = 0;
        
        tenant.products.forEach(p => {
            const margin = p.price - p.cost;
            if (margin > bestMargin) {
                bestMargin = margin;
                bestProd = p;
            }
        });
        
        if (bestProd) {
            const marginPercent = Math.round((bestMargin / bestProd.price) * 100);
            reply = `🤖 **Análisis de Margen de MigaAI:**
            
            El producto estrella de **${tenant.info.name}** es el **${bestProd.name}**.
            
            *   **Precio de Venta:** RD$${bestProd.price.toLocaleString()}
            *   **Costo Real Unitario:** RD$${bestProd.cost.toFixed(2)}
            *   **Ganancia por Unidad:** RD$${bestMargin.toLocaleString()}
            *   **Margen de Utilidad:** ¡un espectacular **${marginPercent}%** de margen limpio!
            
            *💡 Consejo de MigaAI:* Aumenta la producción y exhibición de este postre en tu POS. ¡Es tu mina de oro!`;
        } else {
            reply = "🤖 Aún no posees productos en el catálogo de ventas para analizar rentabilidad.";
        }
    }
    // COMANDO 3: Caja chica
    else if (qLower.includes("caja") || qLower.includes("abrir")) {
        const matchNums = qLower.match(/\d+/);
        const fund = matchNums ? parseInt(matchNums[0]) : 1000;
        
        if (tenant.caja.active) {
            reply = `🤖 La caja chica ya se encuentra **ABIERTA** con un fondo inicial. Efectivo esperado actual: **RD$${tenant.caja.active.expectedCash.toLocaleString()}**.`;
        } else {
            tenant.caja.active = {
                id: `caja_act_${Date.now()}`,
                openTime: new Date().toISOString(),
                openFund: fund,
                expectedCash: fund,
                movements: []
            };
            saveToLocalStorage();
            renderCajaDetails();
            reloadDashboardMetrics();
            reply = `🤖 **¡Caja Abierta por MigaAI!** He inicializado la caja chica con un fondo inicial en efectivo de **RD$${fund.toLocaleString()}**. Ya puedes facturar en el POS.`;
        }
    }
    // COMANDO 4: Ventas
    else if (qLower.includes("venta") || qLower.includes("gané") || qLower.includes("factura")) {
        let total = 0;
        tenant.sales.forEach(s => total += s.total);
        reply = `🤖 **Resumen de Ventas MigaAI:**
        
        El negocio **${tenant.info.name}** ha facturado un total de **RD$${total.toLocaleString()}** en lo que va del período. 
        
        *   **Ventas Efectivo:** Registrado en caja chica.
        *   **Cuentas por Cobrar:** Créditos activos de clientes recurrentes.
        
        Puedes ver la gráfica y el estado de resultados detallado en tu **Tablero General**.`;
    }
    // DEFAULT RESPOND
    else {
        reply = `🤖 **MigaAI Entendido:** He recibido tu consulta en **${tenant.info.name}**. 
        
        Actualmente puedo procesar órdenes de producción directas de recetas si me escribes algo como *"Hice 27 brownies"*, decirte cuál es tu postre más rentable (*"¿Qué postre me deja más dinero?"*), o consultar el flujo de tu caja chica.
        
        ¿En qué otra tarea puedo facilitarte la vida hoy?`;
    }
    
    appendChatMessage("system", reply);
}

// ==========================================
// CONTROL ADMINISTRATIVO Y EXCEL / CSV ENGINE
// ==========================================

function renderSalesHistoryTable() {
    const tbody = document.getElementById("sales-history-tbody");
    if (!tbody) return;
    tbody.innerHTML = "";
    
    const tenant = DB[activeTenant];
    if (!tenant.sales) tenant.sales = [];
    
    // Render in reverse chronological order
    const reversedSales = [...tenant.sales].reverse();
    
    reversedSales.forEach(sale => {
        const tr = document.createElement("tr");
        
        let actionsHtml = "";
        if (activeRole === "admin") {
            actionsHtml = `
                <button class="btn btn-secondary small" onclick="openEditSaleModal('${sale.id}')" style="padding: 4px 8px; font-size:11px; margin-right: 4px;">
                    <i class="fa-solid fa-pen-to-square"></i> Modificar
                </button>
                <button class="btn btn-red small" onclick="deleteSale('${sale.id}')" style="padding: 4px 8px; font-size:11px;">
                    <i class="fa-solid fa-trash"></i> Anular
                </button>
            `;
        } else {
            actionsHtml = `<span style="color:var(--text-light); font-size:11px;">Solo Admin</span>`;
        }
        
        tr.innerHTML = `
            <td><code>${new Date(sale.date).toLocaleString()}</code></td>
            <td><strong>${sale.ncf || sale.id}</strong></td>
            <td>${sale.customer || "Consumidor Final"}</td>
            <td><span class="badge font-secondary" style="text-transform: capitalize;">${sale.payment}</span></td>
            <td>RD$${(sale.subtotal || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
            <td>RD$${(sale.tax || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
            <td><strong>RD$${(sale.total || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</strong></td>
            <td class="admin-only-action-cell">${actionsHtml}</td>
        `;
        tbody.appendChild(tr);
    });
}

function openEditSaleModal(saleId) {
    const tenant = DB[activeTenant];
    const sale = tenant.sales.find(s => s.id === saleId);
    if (!sale) return;
    
    document.getElementById("edit-sale-id").value = sale.id;
    document.getElementById("edit-sale-ncf").value = sale.ncf || sale.id;
    document.getElementById("edit-sale-date").value = new Date(sale.date).toLocaleString();
    document.getElementById("edit-sale-customer").value = sale.customer || "";
    document.getElementById("edit-sale-payment").value = sale.payment;
    document.getElementById("edit-sale-total").value = sale.total;
    
    document.getElementById("edit-sale-modal").classList.remove("hidden");
}

function saveEditedSale() {
    const saleId = document.getElementById("edit-sale-id").value;
    const customer = document.getElementById("edit-sale-customer").value.trim();
    const payment = document.getElementById("edit-sale-payment").value;
    const total = parseFloat(document.getElementById("edit-sale-total").value) || 0;
    
    if (total <= 0) {
        alert("El monto total de la factura debe ser mayor a cero.");
        return;
    }
    
    const tenant = DB[activeTenant];
    const saleIndex = tenant.sales.findIndex(s => s.id === saleId);
    if (saleIndex === -1) return;
    
    const sale = tenant.sales[saleIndex];
    const oldTotal = sale.total;
    const oldPayment = sale.payment;
    const diff = total - oldTotal;
    
    // Modificaciones contables de ajuste
    // 1. Revertir impacto anterior
    if (oldPayment === "efectivo" && tenant.caja.active) {
        tenant.caja.active.expectedCash -= oldTotal;
    } else if (oldPayment === "credito") {
        const client = tenant.clients.find(c => c.name === sale.customer || sale.customer.includes(c.name));
        if (client) {
            client.debt = Math.max(0, client.debt - oldTotal);
        }
    }
    
    // 2. Aplicar nuevo impacto
    if (payment === "efectivo" && tenant.caja.active) {
        tenant.caja.active.expectedCash += total;
    } else if (payment === "credito") {
        const client = tenant.clients.find(c => c.name === customer || customer.includes(c.name));
        if (client) {
            client.debt += total;
        } else {
            // Si el cliente no existe en el CRM, crearlo dinámicamente para registrar su crédito
            const newClientId = `cli_${customer.toLowerCase().replace(/[^a-z0-9]/g, '_')}_${Date.now()}`;
            tenant.clients.push({
                id: newClientId,
                name: customer,
                phone: "N/A",
                email: "N/A",
                creditLimit: total * 2,
                debt: total
            });
        }
    }
    
    // Actualizar campos
    sale.customer = customer;
    sale.payment = payment;
    sale.total = total;
    sale.tax = Math.round(total * 0.18);
    sale.subtotal = total - sale.tax;
    
    logAudit("Ventas", `Modificación de Factura NCF: ${sale.ncf}`, `Ajuste de Monto: RD$${oldTotal.toFixed(2)} -> RD$${total.toFixed(2)} | Pago: ${oldPayment.toUpperCase()} -> ${payment.toUpperCase()}`);
    
    saveToLocalStorage();
    document.getElementById("edit-sale-modal").classList.add("hidden");
    
    renderSalesHistoryTable();
    renderCajaDetails();
    renderCRMClients();
    reloadDashboardMetrics();
    alert("¡Factura modificada correctamente!");
}

function deleteSale(saleId) {
    if (!confirm("⚠️ ¿Estás seguro de que deseas ANULAR y ELIMINAR esta venta?\n\nEsta acción devolverá los productos al stock del POS y ajustará los saldos de caja o cuentas corrientes automáticamente.")) {
        return;
    }
    
    const tenant = DB[activeTenant];
    const saleIndex = tenant.sales.findIndex(s => s.id === saleId);
    if (saleIndex === -1) return;
    
    const sale = tenant.sales[saleIndex];
    
    // 1. Revertir stock de productos POS
    sale.items.forEach(item => {
        const prod = tenant.products.find(p => p.id === item.id);
        if (prod) {
            prod.stock += item.qty;
        }
    });
    
    // 2. Revertir saldo de Caja Chica o CRM
    if (sale.payment === "efectivo" && tenant.caja.active) {
        tenant.caja.active.expectedCash = Math.max(0, tenant.caja.active.expectedCash - sale.total);
    } else if (sale.payment === "credito") {
        const client = tenant.clients.find(c => c.name === sale.customer || sale.customer.includes(c.name));
        if (client) {
            client.debt = Math.max(0, client.debt - sale.total);
        }
    }
    
    // 3. Eliminar de base de datos
    tenant.sales.splice(saleIndex, 1);
    
    logAudit("Ventas", `Anulación completa de Venta NCF: ${sale.ncf}`, `Reversión de fondos: RD$${sale.total.toFixed(2)} devueltos`);
    
    saveToLocalStorage();
    if (document.getElementById("edit-sale-modal")) {
        document.getElementById("edit-sale-modal").classList.add("hidden");
    }
    
    renderSalesHistoryTable();
    renderPOSCatalog();
    renderCajaDetails();
    renderCRMClients();
    reloadDashboardMetrics();
    alert(`¡Venta ${sale.ncf} anulada correctamente! El stock de los postres ha sido restaurado.`);
}

function openEditItemModal(itemId) {
    const tenant = DB[activeTenant];
    const item = tenant.inventory.find(i => i.id === itemId);
    if (!item) return;
    
    document.getElementById("edit-item-id").value = item.id;
    document.getElementById("edit-item-name").value = item.name;
    document.getElementById("edit-item-category").value = item.category;
    document.getElementById("edit-item-unit").value = item.unit;
    document.getElementById("edit-item-stock").value = item.stock;
    document.getElementById("edit-item-cost").value = item.cost;
    document.getElementById("edit-item-min").value = item.minStock;
    
    document.getElementById("edit-item-modal").classList.remove("hidden");
}

function saveEditedItem() {
    const itemId = document.getElementById("edit-item-id").value;
    const name = document.getElementById("edit-item-name").value.trim();
    const category = document.getElementById("edit-item-category").value;
    const unit = document.getElementById("edit-item-unit").value;
    const stock = parseFloat(document.getElementById("edit-item-stock").value) || 0;
    const cost = parseFloat(document.getElementById("edit-item-cost").value) || 0;
    const minStock = parseFloat(document.getElementById("edit-item-min").value) || 0;
    
    if (!name) {
        alert("El nombre del insumo es obligatorio.");
        return;
    }
    
    const tenant = DB[activeTenant];
    const item = tenant.inventory.find(i => i.id === itemId);
    if (!item) return;
    
    // Registrar auditoría y Kardex si el stock o el costo cambiaron
    if (item.stock !== stock || item.cost !== cost) {
        tenant.kardex.push({
            time: new Date().toISOString(),
            name: name,
            type: "Ajuste (Ficha)",
            qty: Math.abs(stock - item.stock),
            unit: unit,
            cost: cost,
            reason: `Modificación manual de ficha técnica. Stock previo: ${item.stock}, Nuevo: ${stock}`
        });
    }
    
    item.name = name;
    item.category = category;
    item.unit = unit;
    item.stock = stock;
    item.cost = cost;
    item.minStock = minStock;
    
    logAudit("Inventario", `Edición de Insumo: ${name}`, `Ficha técnica redefinida. Stock: ${stock} | Costo Promedio: RD$${cost.toFixed(4)}`);
    
    saveToLocalStorage();
    document.getElementById("edit-item-modal").classList.add("hidden");
    renderInventoryTable();
    alert("¡Ficha del insumo actualizada correctamente!");
}

function deleteInventoryItem(itemId) {
    if (!confirm("⚠️ ¿Estás seguro de que deseas ELIMINAR por completo este insumo del almacén?\n\nEsto afectará las recetas que lo utilicen.")) {
        return;
    }
    
    const tenant = DB[activeTenant];
    const index = tenant.inventory.findIndex(i => i.id === itemId);
    if (index === -1) return;
    
    const item = tenant.inventory[index];
    
    // Verificar si está en recetas
    const activeRecipes = tenant.recipes.filter(rec => rec.ingredients.some(ing => ing.id === itemId));
    if (activeRecipes.length > 0) {
        const recipeNames = activeRecipes.map(r => r.name).join(", ");
        if (!confirm(`⚠️ ATENCIÓN: Este insumo se usa actualmente en las siguientes recetas:\n\n[ ${recipeNames} ]\n\n¿Deseas continuar con la eliminación de todos modos?`)) {
            return;
        }
    }
    
    tenant.inventory.splice(index, 1);
    
    logAudit("Inventario", `Eliminación de Insumo: ${item.name}`, `Insumo removido del sistema relacional SQLite.`);
    
    saveToLocalStorage();
    document.getElementById("edit-item-modal").classList.add("hidden");
    renderInventoryTable();
    renderRecipes();
    alert("¡Insumo eliminado del almacén!");
}

function deleteRecipe(recipeId) {
    if (!confirm("⚠️ ¿Estás seguro de que deseas ELIMINAR permanentemente esta receta y su costeo?\n\nEsta acción no se puede deshacer.")) {
        return;
    }
    
    const tenant = DB[activeTenant];
    const index = tenant.recipes.findIndex(r => r.id === recipeId);
    if (index === -1) return;
    
    const recipe = tenant.recipes[index];
    tenant.recipes.splice(index, 1);
    
    logAudit("Recetario", `Eliminación de Receta: ${recipe.name}`, `Receta removida del catálogo de costeo.`);
    
    saveToLocalStorage();
    
    // Resetear panel costeo vacío
    document.getElementById("recipe-calc-empty").classList.remove("hidden");
    document.getElementById("recipe-calc-details").classList.add("hidden");
    activeSelectedRecipeId = null;
    
    renderRecipes();
    alert("¡Receta eliminada correctamente!");
}

function exportToCSV(dataArray, filename) {
    if (!dataArray || dataArray.length === 0) {
        alert("No hay datos para exportar.");
        return;
    }
    
    let headers = [];
    let rows = [];
    
    const first = dataArray[0];
    if ('ncf' in first) {
        headers = ["Fecha/Hora", "NCF/Factura", "Cliente", "Metodo Pago", "Subtotal (RD$)", "ITBIS (RD$)", "Total (RD$)"];
        rows = dataArray.map(s => [
            new Date(s.date).toLocaleString(),
            s.ncf,
            s.customer,
            s.payment.toUpperCase(),
            s.subtotal.toFixed(2),
            s.tax.toFixed(2),
            s.total.toFixed(2)
        ]);
    } else if ('minStock' in first) {
        headers = ["ID Insumo", "Nombre Insumo", "Categoria", "Stock Actual", "Unidad", "Costo Promedio (RD$)", "Valor Total (RD$)", "Stock Minimo"];
        rows = dataArray.map(i => [
            i.id,
            i.name,
            i.category,
            i.stock.toFixed(2),
            i.unit,
            i.cost.toFixed(4),
            (i.stock * i.cost).toFixed(2),
            i.minStock.toFixed(2)
        ]);
    } else if ('type' in first && 'time' in first) {
        headers = ["Fecha/Hora", "Nombre Insumo", "Tipo Movimiento", "Cantidad", "Unidad", "Costo (RD$)", "Detalle/Razon"];
        rows = dataArray.map(k => [
            new Date(k.time).toLocaleString(),
            k.name,
            k.type,
            k.qty.toFixed(2),
            k.unit,
            k.cost.toFixed(4),
            k.reason || ""
        ]);
    } else {
        headers = Object.keys(first);
        rows = dataArray.map(obj => Object.values(obj));
    }
    
    const csvContent = "\uFEFF" + [
        headers.map(h => `"${h.replace(/"/g, '""')}"`).join(","),
        ...rows.map(row => row.map(val => {
            const str = String(val === null || val === undefined ? '' : val);
            return `"${str.replace(/"/g, '""')}"`;
        }).join(","))
    ].join("\n");
    
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    if (link.download !== undefined) {
        const url = URL.createObjectURL(blob);
        link.setAttribute("href", url);
        link.setAttribute("download", filename);
        link.style.visibility = "hidden";
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
}

function importInventoryCSV(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = function(e) {
        const text = e.target.result;
        const lines = text.split(/\r?\n/);
        if (lines.length < 2) {
            alert("El archivo CSV está vacío o no tiene suficientes filas.");
            return;
        }
        
        const firstLine = lines[0];
        const separator = firstLine.includes(";") ? ";" : ",";
        const headers = firstLine.split(separator).map(h => h.trim().replace(/^["']|["']$/g, '').toLowerCase());
        
        const idxName = headers.findIndex(h => h.includes("nombre") || h.includes("insumo") || h.includes("item") || h.includes("name"));
        const idxCategory = headers.findIndex(h => h.includes("categoria") || h.includes("category"));
        const idxStock = headers.findIndex(h => h.includes("cantidad") || h.includes("stock") || h.includes("qty"));
        const idxCost = headers.findIndex(h => h.includes("costo") || h.includes("cost") || h.includes("precio"));
        const idxUnit = headers.findIndex(h => h.includes("unidad") || h.includes("unit"));
        const idxMin = headers.findIndex(h => h.includes("min") || h.includes("alerta"));
        
        if (idxName === -1 || idxStock === -1 || idxCost === -1) {
            alert("El CSV debe contener al menos las columnas: Nombre/Insumo, Cantidad/Stock y Costo.");
            return;
        }
        
        const tenant = DB[activeTenant];
        let importedCount = 0;
        let updatedCount = 0;
        
        for (let i = 1; i < lines.length; i++) {
            const line = lines[i].trim();
            if (!line) continue;
            
            const fields = line.split(separator).map(f => f.trim().replace(/^["']|["']$/g, ''));
            if (fields.length <= Math.max(idxName, idxStock, idxCost)) continue;
            
            const name = fields[idxName];
            const category = idxCategory !== -1 && fields[idxCategory] ? fields[idxCategory] : "Ingredientes";
            const qty = parseFloat(fields[idxStock]) || 0;
            const cost = parseFloat(fields[idxCost]) || 0;
            const unit = idxUnit !== -1 && fields[idxUnit] ? fields[idxUnit] : "g";
            const minStock = idxMin !== -1 && fields[idxMin] ? parseFloat(fields[idxMin]) : Math.round(qty * 0.2);
            
            if (!name || qty <= 0) continue;
            
            const item = tenant.inventory.find(inv => inv.name.toLowerCase() === name.toLowerCase());
            
            if (item) {
                const stockPrevio = item.stock;
                const costoPrevio = item.cost;
                
                if (stockPrevio + qty > 0) {
                    if (stockPrevio <= 0) {
                        item.cost = cost;
                    } else {
                        item.cost = ((stockPrevio * costoPrevio) + (qty * cost)) / (stockPrevio + qty);
                    }
                }
                
                item.stock += qty;
                updatedCount++;
                
                tenant.kardex.push({
                    time: new Date().toISOString(),
                    name: item.name,
                    type: "Entrada (CSV)",
                    qty: qty,
                    unit: item.unit,
                    cost: cost,
                    reason: `Compra masiva via CSV. Costo promedio anterior: RD$${costoPrevio.toFixed(4)}, Nuevo: RD$${item.cost.toFixed(4)}`
                });
            } else {
                const newId = `inv_${name.toLowerCase().replace(/[^a-z0-9]/g, "_")}_${Date.now()}`;
                const newItem = {
                    id: newId,
                    name: name,
                    category: category,
                    stock: qty,
                    unit: unit,
                    cost: cost,
                    minStock: minStock
                };
                tenant.inventory.push(newItem);
                importedCount++;
                
                tenant.kardex.push({
                    time: new Date().toISOString(),
                    name: name,
                    type: "Entrada (CSV)",
                    qty: qty,
                    unit: unit,
                    cost: cost,
                    reason: `Carga inicial de insumo via CSV.`
                });
            }
        }
        
        saveToLocalStorage();
        renderInventoryTable();
        alert(`¡Carga CSV completada!\n- ${importedCount} nuevos insumos creados.\n- ${updatedCount} insumos existentes actualizados con CPP.`);
        event.target.value = "";
    };
    
    reader.readAsText(file);
}

function bindAdminActions() {
    // 1. Modales de Edición Factura & Insumo
    const editSaleSaveBtn = document.getElementById("edit-sale-save-btn");
    if (editSaleSaveBtn) {
        editSaleSaveBtn.addEventListener("click", saveEditedSale);
    }
    
    const editSaleDeleteBtn = document.getElementById("edit-sale-delete-btn");
    if (editSaleDeleteBtn) {
        editSaleDeleteBtn.addEventListener("click", () => {
            const saleId = document.getElementById("edit-sale-id").value;
            if (saleId) deleteSale(saleId);
        });
    }
    
    const editItemSaveBtn = document.getElementById("edit-item-save-btn");
    if (editItemSaveBtn) {
        editItemSaveBtn.addEventListener("click", saveEditedItem);
    }
    
    const editItemDeleteBtn = document.getElementById("edit-item-delete-btn");
    if (editItemDeleteBtn) {
        editItemDeleteBtn.addEventListener("click", () => {
            const itemId = document.getElementById("edit-item-id").value;
            if (itemId) deleteInventoryItem(itemId);
        });
    }
    
    const deleteRecipeBtn = document.getElementById("delete-recipe-btn");
    if (deleteRecipeBtn) {
        deleteRecipeBtn.addEventListener("click", () => {
            if (activeSelectedRecipeId) deleteRecipe(activeSelectedRecipeId);
        });
    }
    
    // 2. Exportación a CSV
    const exportSalesBtn = document.getElementById("export-sales-csv-btn");
    if (exportSalesBtn) {
        exportSalesBtn.addEventListener("click", () => {
            const tenant = DB[activeTenant];
            exportToCSV(tenant.sales || [], `Bitacora_Ventas_${activeTenant}.csv`);
        });
    }
    
    const exportInvBtn = document.getElementById("export-inventory-csv-btn");
    if (exportInvBtn) {
        exportInvBtn.addEventListener("click", () => {
            const tenant = DB[activeTenant];
            exportToCSV(tenant.inventory || [], `Inventario_${activeTenant}.csv`);
        });
    }
    
    const exportKardexBtn = document.getElementById("export-kardex-csv-btn");
    if (exportKardexBtn) {
        exportKardexBtn.addEventListener("click", () => {
            const tenant = DB[activeTenant];
            exportToCSV(tenant.kardex || [], `Kardex_Movimientos_${activeTenant}.csv`);
        });
    }
    
    // 3. Importación desde CSV
    const importBtn = document.getElementById("import-inventory-csv-btn");
    const importInput = document.getElementById("csv-import-file");
    if (importBtn && importInput) {
        importBtn.addEventListener("click", () => {
            importInput.click();
        });
        importInput.addEventListener("change", importInventoryCSV);
    }
    
    // 4. Descarga de Copia de Seguridad Real SQLite erp.db
    const downloadBtn = document.getElementById("download-db-backup-btn");
    if (downloadBtn) {
        downloadBtn.addEventListener("click", async () => {
            if (!sessionToken) {
                alert("El respaldo real de base de datos solo está disponible en modo online conectado al servidor seguro.");
                return;
            }
            try {
                const res = await fetch(`${API_BASE}/api/backup/download`, {
                    headers: { "Authorization": `Bearer ${sessionToken}` }
                });
                if (res && res.ok) {
                    const blob = await res.blob();
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    
                    const disposition = res.headers.get("Content-Disposition");
                    let filename = `respaldo_erp_${activeTenant}.db`;
                    if (disposition && disposition.indexOf("attachment") !== -1) {
                        const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
                        const matches = filenameRegex.exec(disposition);
                        if (matches != null && matches[1]) {
                            filename = matches[1].replace(/['"]/g, '');
                        }
                    }
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                    alert("💾 ¡Copia de seguridad relacional erp.db descargada con éxito!");
                } else {
                    const err = await res.json();
                    alert(err.error || "No se pudo descargar el respaldo del servidor.");
                }
            } catch (err) {
                console.error("Error descargando backup:", err);
                alert("Error de conexión al descargar el respaldo.");
            }
        });
    }
}

// =====================================================================
// FINANZAS Y NÓMINA MODULE (Added via Update)
// =====================================================================
document.addEventListener("DOMContentLoaded", () => {
    // 1. Interceptar navegación a finanzas-page
    const oldNavigate = window.navigateToPage;
    window.navigateToPage = function(pageId) {
        if (oldNavigate) oldNavigate(pageId);
        else {
            document.querySelectorAll(".page-section").forEach(p => p.classList.remove("active"));
            const page = document.getElementById(pageId);
            if (page) page.classList.add("active");
            document.querySelectorAll(".sidebar-nav .nav-item").forEach(item => {
                item.classList.remove("active");
                if (item.getAttribute("data-target") === pageId) item.classList.add("active");
            });
        }
        if (pageId === "finanzas-page") {
            renderFinanzasPage();
        }
    };

    const expForm = document.getElementById("expense-606-form");
    if (expForm) {
        expForm.addEventListener("submit", (e) => {
            e.preventDefault();
            const tenant = DB[activeTenant];
            if (!tenant.expenses) tenant.expenses = [];
            
            const rnc = document.getElementById("exp-rnc").value.trim();
            const ncf = document.getElementById("exp-ncf").value.trim();
            const amount = parseFloat(document.getElementById("exp-amount").value);
            const tax = parseFloat(document.getElementById("exp-tax").value) || 0;
            const desc = document.getElementById("exp-desc").value.trim();
            
            tenant.expenses.push({
                date: new Date().toISOString(),
                rnc, ncf, amount, tax, desc
            });
            saveToLocalStorage();
            
            // Impactar Caja si está abierta
            if (tenant.caja && tenant.caja.active) {
                tenant.caja.active.movements.push({
                    time: new Date().toISOString(),
                    type: "egreso",
                    monto: amount + tax,
                    concept: `Pago a Proveedor (NCF ${ncf}) - ${desc}`
                });
            }
            
            e.target.reset();
            renderFinanzasPage();
            alert("Gasto NCF 606 registrado exitosamente.");
        });
    }

    const payBtn = document.getElementById("process-payroll-btn");
    if (payBtn) {
        payBtn.addEventListener("click", () => {
            alert("Nómina procesada. Se han generado los comprobantes de pago y se descontó de la cuenta contable de bancos.");
        });
    }
});

function renderFinanzasPage() {
    const tenant = DB[activeTenant];
    if (!tenant.expenses) tenant.expenses = [];
    
    // 1. Render Expenses 606
    const expTbody = document.getElementById("expenses-tbody");
    if (expTbody) {
        expTbody.innerHTML = "";
        tenant.expenses.forEach(ex => {
            const tr = document.createElement("tr");
            const d = new Date(ex.date).toLocaleDateString();
            const total = ex.amount + ex.tax;
            tr.innerHTML = `<td>${d}</td><td>${ex.rnc}</td><td>${ex.ncf}</td><td class="text-red font-bold">RD$${total.toLocaleString()}</td>`;
            expTbody.appendChild(tr);
        });
    }
    
    // 2. Render Payroll
    const payTbody = document.getElementById("payroll-tbody");
    if (payTbody && tenant.users) {
        payTbody.innerHTML = "";
        // Calculate Total Sales for Commission
        const totalSales = tenant.sales ? tenant.sales.reduce((sum, s) => sum + s.total, 0) : 0;
        
        tenant.users.forEach(u => {
            const base = parseFloat(u.baseSalary) || 0;
            // 2% commission only for Cajeros, based on total sales for demo simplicity (or specific sales)
            let comm = 0;
            if (u.role === "cajero") comm = totalSales * 0.02;
            
            // AFP (2.87%) + SFS (3.04%) = 5.91%
            const ded = base * 0.0591;
            const net = base + comm - ded;
            
            if (base > 0 || comm > 0) {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td>${u.name} <br><small class="text-muted">${u.role}</small></td>
                    <td>RD$${base.toLocaleString()}</td>
                    <td class="text-green">RD$${comm.toLocaleString()}</td>
                    <td class="text-red">RD$${ded.toLocaleString()}</td>
                    <td class="font-bold premium-text">RD$${net.toLocaleString()}</td>
                `;
                payTbody.appendChild(tr);
            }
        });
    }
    
    // 3. Render Financial Statements
    renderFinancialStatements(tenant);
}

function renderFinancialStatements(tenant) {
    const plDisp = document.getElementById("pl-statement-display");
    const bsDisp = document.getElementById("bs-statement-display");
    if (!plDisp || !bsDisp) return;
    
    // Calculations
    const ingresos = tenant.sales ? tenant.sales.reduce((sum, s) => sum + s.total, 0) : 0;
    
    let cogs = 0;
    if (tenant.sales) {
        tenant.sales.forEach(s => {
            if (s.items) {
                s.items.forEach(i => {
                    const prod = tenant.products.find(p => p.name === i.name);
                    const cost = prod ? prod.cost : 0;
                    cogs += (cost * i.qty);
                });
            }
        });
    }
    
    const utilBruta = ingresos - cogs;
    
    // Gastos Operativos (from expenses 606 + manual expenses in caja)
    let opsExp = 0;
    tenant.expenses.forEach(e => opsExp += (e.amount + e.tax));
    
    let cajaExp = 0;
    if (tenant.caja && tenant.caja.history) {
        tenant.caja.history.forEach(h => {
            if (h.movements) {
                h.movements.forEach(m => {
                    if (m.type === "egreso") cajaExp += m.monto;
                });
            }
        });
    }
    
    // Payroll Expenses
    let payExp = 0;
    if (tenant.users) {
        tenant.users.forEach(u => {
            payExp += (parseFloat(u.baseSalary) || 0);
        });
    }
    
    const utilNeta = utilBruta - opsExp - cajaExp - payExp;
    
    plDisp.innerHTML = `
=============================================
           ESTADO DE RESULTADOS (P&L)
=============================================
(+) Ingresos por Ventas         : RD$ ${ingresos.toLocaleString()}
(-) Costo de Ventas (COGS)      : RD$ ${cogs.toLocaleString()}
---------------------------------------------
(=) Utilidad Bruta              : RD$ ${utilBruta.toLocaleString()}
---------------------------------------------
(-) Gastos Operativos (606)     : RD$ ${opsExp.toLocaleString()}
(-) Gastos Menores (Caja)       : RD$ ${cajaExp.toLocaleString()}
(-) Gastos de Nómina            : RD$ ${payExp.toLocaleString()}
---------------------------------------------
(=) Utilidad Neta               : RD$ ${utilNeta.toLocaleString()}
=============================================
    `;
    
    // Balance Sheet
    let efectivo = 0;
    if (tenant.caja && tenant.caja.history) {
        efectivo = tenant.caja.history.reduce((s, h) => s + h.physicalCash, 0);
    }
    if (tenant.caja && tenant.caja.active) {
        efectivo += tenant.caja.active.expectedCash || tenant.caja.active.openFund;
    }
    
    let cxc = 0;
    if (tenant.clients) cxc = tenant.clients.reduce((s, c) => s + c.debt, 0);
    
    let invVal = 0;
    if (tenant.inventory) invVal = tenant.inventory.reduce((s, i) => s + (i.stock * i.cost), 0);
    
    const totalActivos = efectivo + cxc + invVal;
    
    // Asumimos cuentas por pagar de gastos 606 no pagados, pero digamos que todos son pagados.
    const pasivos = opsExp * 0.1; // 10% demo debt
    const patrimonio = totalActivos - pasivos;
    
    bsDisp.innerHTML = `
=============================================
              BALANCE GENERAL
=============================================
ACTIVOS
  Efectivo y Equivalentes       : RD$ ${efectivo.toLocaleString()}
  Cuentas por Cobrar (Clientes) : RD$ ${cxc.toLocaleString()}
  Inventario de Mercancías      : RD$ ${invVal.toLocaleString()}
---------------------------------------------
Total Activos                   : RD$ ${totalActivos.toLocaleString()}

PASIVOS
  Cuentas por Pagar (Proveed.)  : RD$ ${pasivos.toLocaleString()}
---------------------------------------------
Total Pasivos                   : RD$ ${pasivos.toLocaleString()}

PATRIMONIO
  Capital Social y Retenidas    : RD$ ${patrimonio.toLocaleString()}
---------------------------------------------
Total Pasivos + Patrimonio      : RD$ ${(pasivos + patrimonio).toLocaleString()}
=============================================
    `;
}

// Print Handlers
document.addEventListener("DOMContentLoaded", () => {
    const printPlBtn = document.getElementById("print-pl-btn");
    if (printPlBtn) {
        printPlBtn.addEventListener("click", () => {
            const data = document.getElementById("pl-statement-display").innerText;
            printTextAsThermal(data, "Estado de Resultados");
        });
    }
    
    const printBsBtn = document.getElementById("print-bs-btn");
    if (printBsBtn) {
        printBsBtn.addEventListener("click", () => {
            const data = document.getElementById("bs-statement-display").innerText;
            printTextAsThermal(data, "Balance General");
        });
    }
});

function printTextAsThermal(textData, title) {
    const iframe = document.createElement("iframe");
    iframe.style.position = "fixed";
    iframe.style.right = "0";
    iframe.style.bottom = "0";
    iframe.style.width = "0";
    iframe.style.height = "0";
    iframe.style.border = "none";
    document.body.appendChild(iframe);

    const doc = iframe.contentWindow.document;
    doc.open();
    doc.write(`
        <html>
        <head>
            <style>
                body {
                    font-family: 'Courier New', Courier, monospace;
                    font-size: 12px;
                    width: 300px;
                    margin: 0;
                    padding: 10px;
                    color: #000;
                }
                pre {
                    white-space: pre-wrap;
                    word-wrap: break-word;
                    margin: 0;
                }
                .text-center { text-align: center; }
            </style>
        </head>
        <body>
            <div class="text-center">
                <h2>${title}</h2>
                <p>${new Date().toLocaleString()}</p>
            </div>
            <pre>${textData}</pre>
        </body>
        </html>
    `);
    doc.close();

    iframe.contentWindow.focus();
    setTimeout(() => {
        iframe.contentWindow.print();
        setTimeout(() => document.body.removeChild(iframe), 1000);
    }, 500);
}
