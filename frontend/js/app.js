const API = '';
let map, markersLayer, polylinesLayer;
let currentResult = null;

const TYPE_COLORS = {
    Depot: '#6366F1', Hotel: '#F59E0B', Travel: '#10B981',
    Culture: '#8B5CF6', OTOP: '#EF4444', Food: '#EC4899'
};
const TYPE_ICONS = {
    Depot: 'fa-plane', Hotel: 'fa-bed', Travel: 'fa-camera',
    Culture: 'fa-landmark', OTOP: 'fa-shopping-bag', Food: 'fa-utensils'
};
const DAY_COLORS = ['#3B82F6', '#EF4444', '#10B981', '#F59E0B'];

document.addEventListener('DOMContentLoaded', () => {
    initMap();
    checkDataStatus();
    loadAllPoints();
});

function initMap() {
    map = L.map('map').setView([8.40, 99.78], 11);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap'
    }).addTo(map);
    markersLayer = L.layerGroup().addTo(map);
    polylinesLayer = L.layerGroup().addTo(map);
}

function createIcon(type, dayColor) {
    const color = dayColor || TYPE_COLORS[type] || '#6B7280';
    const icon = TYPE_ICONS[type] || 'fa-map-pin';
    return L.divIcon({
        html: `<div style="background:${color};width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;border:2px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3)"><i class="fas ${icon}" style="color:white;font-size:12px"></i></div>`,
        className: '', iconSize: [28, 28], iconAnchor: [14, 14]
    });
}

function createNumberedIcon(num, color) {
    return L.divIcon({
        html: `<div style="background:${color};width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;border:2px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3);color:white;font-weight:bold;font-size:12px">${num}</div>`,
        className: '', iconSize: [28, 28], iconAnchor: [14, 14]
    });
}

async function checkDataStatus() {
    try {
        const res = await fetch(`${API}/api/v1/files/validate`, { method: 'POST' });
        const data = await res.json();
        const el = document.getElementById('dataStatus');
        if (data.valid) {
            el.innerHTML = `<i class="fas fa-circle text-green-500 text-xs"></i> ${data.total_records} places loaded`;
        } else {
            el.innerHTML = `<i class="fas fa-circle text-red-500 text-xs"></i> Data errors`;
        }
    } catch (e) {
        console.error('Status check failed:', e);
    }
}

async function loadAllPoints() {
    try {
        const res = await fetch(`${API}/api/v1/map/points`);
        const data = await res.json();
        if (data.items) {
            data.items.forEach(p => {
                const marker = L.marker([p.lat, p.lng], { icon: createIcon(p.type) })
                    .bindPopup(`<b>${p.name}</b><br>Type: ${p.type}<br>Rate: ${p.rate}<br>Visit: ${p.visit_time} min`);
                markersLayer.addLayer(marker);
            });
        }
        const legendRes = await fetch(`${API}/api/v1/map/legend`);
        const legendData = await legendRes.json();
        const bar = document.getElementById('legendBar');
        bar.innerHTML = legendData.items.map(l =>
            `<span class="flex items-center gap-1"><span style="background:${l.color}" class="w-3 h-3 rounded-full inline-block"></span>${l.label}</span>`
        ).join('');
    } catch (e) {
        console.error('Load points failed:', e);
    }
}

function switchTab(tabName) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active', 'bg-blue-500', 'text-white');
        btn.classList.add('bg-gray-200', 'text-gray-700');
    });
    document.getElementById(`tab-${tabName}`).classList.remove('hidden');
    const btns = document.querySelectorAll('.tab-btn');
    const idx = { optimize: 0, results: 1, compare: 2, import: 3 }[tabName];
    if (btns[idx]) {
        btns[idx].classList.add('active');
        btns[idx].classList.remove('bg-gray-200', 'text-gray-700');
    }
    if (tabName === 'results') loadResultsList();
    if (tabName === 'import') checkGoogleStatus();
}

// ─── Google Distance Matrix ────────────────────────────────────────────────

async function checkGoogleStatus() {
    try {
        const res = await fetch(`${API}/api/v1/files/matrix/google/status`);
        const data = await res.json();
        const badge = document.getElementById('googleStatusBadge');
        const cacheInfo = document.getElementById('googleCacheInfo');
        const cacheText = document.getElementById('googleCacheText');
        const btnCached = document.getElementById('btnLoadCached');
        const btnClear = document.getElementById('btnClearGoogle');

        if (data.using_google) {
            badge.className = 'text-xs px-3 py-1 rounded-full bg-green-100 text-green-700 flex items-center gap-1';
            badge.innerHTML = '<i class="fas fa-circle text-xs"></i> ใช้ Google API อยู่';
        } else if (data.cached) {
            badge.className = 'text-xs px-3 py-1 rounded-full bg-yellow-100 text-yellow-700 flex items-center gap-1';
            badge.innerHTML = '<i class="fas fa-circle text-xs"></i> มี Cache (ยังไม่โหลด)';
        } else {
            badge.className = 'text-xs px-3 py-1 rounded-full bg-gray-100 text-gray-500 flex items-center gap-1';
            badge.innerHTML = '<i class="fas fa-circle text-xs"></i> ใช้ Haversine';
        }

        if (data.cached) {
            cacheInfo.classList.remove('hidden');
            cacheText.textContent = `มีไฟล์ Cache อยู่แล้ว — บันทึกเมื่อ: ${data.last_updated || 'ไม่ทราบ'}`;
            btnCached.classList.remove('hidden');
            btnClear.classList.remove('hidden');
        } else {
            cacheInfo.classList.add('hidden');
            btnCached.classList.add('hidden');
            btnClear.classList.add('hidden');
        }
    } catch (e) {
        console.error('Google status check failed:', e);
    }
}

function toggleApiKeyVisibility() {
    const input = document.getElementById('googleApiKey');
    const icon = document.getElementById('apiKeyEyeIcon');
    if (input.type === 'password') {
        input.type = 'text';
        icon.className = 'fas fa-eye-slash';
    } else {
        input.type = 'password';
        icon.className = 'fas fa-eye';
    }
}

function setGoogleStatusMsg(msg, type = 'info') {
    const el = document.getElementById('googleStatus');
    el.classList.remove('hidden');
    const colors = {
        info:    'text-blue-700 bg-blue-50 border-blue-100',
        success: 'text-green-700 bg-green-50 border-green-100',
        error:   'text-red-700 bg-red-50 border-red-100',
    };
    el.className = `text-sm p-3 rounded-lg border ${colors[type] || colors.info}`;
    el.innerHTML = msg;
}

async function loadGoogleMatrix() {
    const apiKey = document.getElementById('googleApiKey').value.trim();
    if (!apiKey) {
        setGoogleStatusMsg('<i class="fas fa-exclamation-triangle mr-1"></i> กรุณากรอก Google API Key ก่อน', 'error');
        return;
    }

    const btn = document.getElementById('btnLoadGoogle');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> กำลังดึงข้อมูล...';

    const progress = document.getElementById('googleProgress');
    const progressBar = document.getElementById('googleProgressBar');
    const progressText = document.getElementById('googleProgressText');
    progress.classList.remove('hidden');

    // Simulate progress during long API call
    let pct = 0;
    const ticker = setInterval(() => {
        pct = Math.min(pct + Math.random() * 8, 90);
        progressBar.style.width = pct + '%';
        progressText.textContent = Math.round(pct) + '%';
    }, 600);

    setGoogleStatusMsg('<i class="fas fa-satellite-dish mr-1"></i> กำลังเรียก Google Distance Matrix API... (44×44 = 1,936 คู่)', 'info');

    try {
        const res = await fetch(`${API}/api/v1/files/matrix/google`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: apiKey })
        });
        const data = await res.json();

        clearInterval(ticker);
        progressBar.style.width = '100%';
        progressText.textContent = '100%';

        if (!res.ok) throw new Error(data.detail || 'API Error');

        setGoogleStatusMsg(
            `<i class="fas fa-check-circle mr-1"></i> สำเร็จ! ดึง ${data.matrix_size}×${data.matrix_size} matrix (${data.api_calls} API calls) — บันทึกเป็น Cache แล้ว`,
            'success'
        );
        document.getElementById('googleApiKey').value = '';
        await checkGoogleStatus();
        checkDataStatus();
    } catch (e) {
        clearInterval(ticker);
        setGoogleStatusMsg(`<i class="fas fa-times-circle mr-1"></i> Error: ${e.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-satellite-dish"></i> ดึงข้อมูลจาก Google API';
        setTimeout(() => {
            progress.classList.add('hidden');
            progressBar.style.width = '0%';
        }, 2000);
    }
}

async function loadCachedMatrix() {
    const btn = document.getElementById('btnLoadCached');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> กำลังโหลด...';
    try {
        // Reload cache by POSTing with empty api_key won't work — 
        // instead restart the server or just inform that it's already auto-loaded
        setGoogleStatusMsg(
            '<i class="fas fa-bolt mr-1"></i> Cache โหลดอัตโนมัติตอนเซิร์ฟเวอร์เริ่ม — รีสตาร์ทเซิร์ฟเวอร์เพื่อโหลดใหม่ หรือคลิก "ดึงข้อมูลจาก Google API" เพื่ออัปเดต',
            'info'
        );
        await checkGoogleStatus();
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-bolt"></i> โหลด Cache ที่บันทึกไว้';
    }
}

async function clearGoogleCache() {
    if (!confirm('ต้องการล้าง Cache และกลับไปใช้ Haversine ใช่ไหม?')) return;
    const btn = document.getElementById('btnClearGoogle');
    btn.disabled = true;
    try {
        const res = await fetch(`${API}/api/v1/files/matrix/google/cache`, { method: 'DELETE' });
        const data = await res.json();
        setGoogleStatusMsg(
            `<i class="fas fa-check-circle mr-1"></i> ล้าง Cache แล้ว (${data.deleted.join(', ')}) — กลับไปใช้ Haversine`,
            'success'
        );
        await checkGoogleStatus();
    } catch (e) {
        setGoogleStatusMsg(`<i class="fas fa-times-circle mr-1"></i> Error: ${e.message}`, 'error');
    } finally {
        btn.disabled = false;
    }
}

async function runOptimize() {
    const btn = document.getElementById('btnOptimize');
    btn.innerHTML = '<span class="spinner"></span> กำลังคำนวณ...';
    btn.disabled = true;

    const body = {
        trip_days: parseInt(document.getElementById('tripDays').value),
        algorithm: document.getElementById('algorithm').value,
        lifestyle_type: document.getElementById('lifestyle').value,
        min_places_per_day: parseInt(document.getElementById('minPlaces').value),
        max_places_per_day: parseInt(document.getElementById('maxPlaces').value),
        weight_distance: parseFloat(document.getElementById('wDist').value),
        weight_co2: parseFloat(document.getElementById('wCo2').value),
        weight_rating: parseFloat(document.getElementById('wRating').value),
    };

    try {
        const res = await fetch(`${API}/api/v1/routes/optimize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Optimization failed');

        const fullRes = await fetch(`${API}/api/v1/results/${data.result_id}`);
        currentResult = await fullRes.json();
        displayResult(currentResult);
    } catch (e) {
        alert('Error: ' + e.message);
    } finally {
        btn.innerHTML = '<i class="fas fa-play"></i> คำนวณเส้นทาง';
        btn.disabled = false;
    }
}

function displayResult(result) {
    document.getElementById('summaryCards').classList.remove('hidden');
    document.getElementById('sumDist').textContent = result.summary.total_distance_km.toFixed(2);
    document.getElementById('sumTime').textContent = result.summary.total_time_min.toFixed(1);
    document.getElementById('sumCo2').textContent = result.summary.total_co2_kg.toFixed(3);
    document.getElementById('sumHotel').textContent = result.summary.selected_hotel || '-';

    markersLayer.clearLayers();
    polylinesLayer.clearLayers();

    const mapData = result.map_data;
    if (mapData.center) {
        map.setView(mapData.center, mapData.zoom || 11);
    }

    if (mapData.days) {
        mapData.days.forEach((day, di) => {
            const color = day.color || DAY_COLORS[di];
            if (day.polyline && day.polyline.length > 1) {
                const polyline = L.polyline(day.polyline, {
                    color: color, weight: 4, opacity: 0.8,
                    dashArray: di > 0 ? '10, 8' : null
                });
                polylinesLayer.addLayer(polyline);
            }
            if (day.markers) {
                day.markers.forEach((m, mi) => {
                    const icon = (mi === 0 || mi === day.markers.length - 1)
                        ? createIcon(m.type, color)
                        : createNumberedIcon(mi, color);
                    const marker = L.marker([m.lat, m.lng], { icon })
                        .bindPopup(`
                            <b>${m.name}</b><br>
                            <span style="color:${color}">วัน ${day.day_no}</span> | ลำดับ ${m.order_in_day || '-'}<br>
                            Type: ${m.type}<br>
                            ${m.arrival_time ? 'เวลาถึง: ' + m.arrival_time : ''}
                            ${m.departure_time ? '<br>เวลาออก: ' + m.departure_time : ''}
                        `);
                    markersLayer.addLayer(marker);
                });
            }
        });
    }

    const dayDetails = document.getElementById('dayDetails');
    dayDetails.innerHTML = '';
    result.days.forEach((day, di) => {
        const color = DAY_COLORS[di];
        const gmapsUrl = buildGoogleMapsUrl(day, result);
        let html = `
            <div class="card p-4 fade-in">
                <div class="flex items-center gap-3 mb-3">
                    <span class="day-badge" style="background:${color}20;color:${color}">วันที่ ${day.day_no}</span>
                    <span class="text-xs text-gray-500 flex-1">${day.distance_km.toFixed(2)} km | ${day.time_min.toFixed(1)} min | CO₂ ${day.co2_kg.toFixed(3)} kg</span>
                    <a href="${gmapsUrl}" target="_blank" rel="noopener noreferrer"
                       class="flex items-center gap-1.5 text-xs bg-green-600 hover:bg-green-700 text-white px-3 py-1.5 rounded-lg transition-colors shadow-sm">
                        <i class="fab fa-google mr-0.5"></i> ดูบน Google Maps
                    </a>
                </div>
                <div class="space-y-1">
        `;
        day.places.forEach((p, idx) => {
            const typeColor = TYPE_COLORS[p.type] || '#6B7280';
            
            // คำนวณเวลาเข้าชม
            const visitDuration = p.visit_time || 0;
            
            html += `
                <div class="border-l-2 pl-3 py-2 hover:bg-gray-50 rounded-r" style="border-color:${color}">
                    <div class="flex items-center gap-3 mb-1">
                        <span class="w-7 h-7 rounded-full flex items-center justify-center text-white text-xs font-bold shadow-sm" style="background:${color}">${p.order}</span>
                        <span class="font-medium flex-1">${p.name}</span>
                        <span class="text-xs px-2 py-0.5 rounded-full font-medium" style="background:${typeColor}20;color:${typeColor}">${p.type}</span>
                    </div>
                    <div class="ml-10 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
                        <span><i class="fas fa-clock text-blue-500 mr-1"></i>เข้าชม: <b class="text-gray-700">${visitDuration} นาที</b></span>
                        <span><i class="fas fa-sign-in-alt text-green-500 mr-1"></i>ถึง: <b class="text-gray-700">${p.arrival}</b></span>
                        <span><i class="fas fa-sign-out-alt text-orange-500 mr-1"></i>ออก: <b class="text-gray-700">${p.departure}</b></span>
                        ${p.travel_time_to_next ? `<span><i class="fas fa-car text-purple-500 mr-1"></i>เดินทางต่อไป: <b class="text-gray-700">${p.travel_time_to_next.toFixed(0)} นาที</b></span>` : ''}
                    </div>
                </div>
            `;
        });
        html += '</div></div>';
        dayDetails.innerHTML += html;
    });

    const exportHtml = `
        <div class="card p-4 fade-in flex items-center gap-3">
            <span class="text-sm text-gray-600 font-medium">ส่งออก:</span>
            <button onclick="exportResult('json')" class="text-sm bg-blue-100 text-blue-700 px-3 py-1 rounded-lg hover:bg-blue-200">JSON</button>
            <button onclick="exportResult('csv')" class="text-sm bg-green-100 text-green-700 px-3 py-1 rounded-lg hover:bg-green-200">CSV</button>
            <span class="text-xs text-gray-400 ml-auto">ID: ${result.result_id}</span>
        </div>
    `;
    dayDetails.innerHTML += exportHtml;

    // แสดง Google Maps route embed
    showGoogleMapsEmbed(result);
}

const DAY_COLORS_HEX = ['#3B82F6', '#EF4444', '#10B981', '#F59E0B'];

function showGoogleMapsEmbed(result) {
    const panel = document.getElementById('gmapsPanel');
    const tabsEl = document.getElementById('gmapsDayTabs');
    panel.classList.remove('hidden');

    // สร้าง tab ปุ่มสำหรับแต่ละวัน
    tabsEl.innerHTML = '';
    result.days.forEach((day, di) => {
        const color = DAY_COLORS_HEX[di] || '#3B82F6';
        const btn = document.createElement('button');
        btn.className = `day-tab-btn ${di === 0 ? 'active' : ''}`;
        btn.style.background = di === 0 ? color : '#F3F4F6';
        btn.style.color = di === 0 ? 'white' : '#374151';
        btn.style.borderColor = color;
        btn.textContent = `วันที่ ${day.day_no}`;
        btn.onclick = () => switchGmapsDay(result, di);
        tabsEl.appendChild(btn);
    });

    // แสดงวันแรกเป็น default
    switchGmapsDay(result, 0);
}

function switchGmapsDay(result, dayIndex) {
    const day = result.days[dayIndex];
    const color = DAY_COLORS_HEX[dayIndex] || '#3B82F6';

    // อัปเดต tab active state
    const tabs = document.querySelectorAll('.day-tab-btn');
    tabs.forEach((btn, i) => {
        const c = DAY_COLORS_HEX[i] || '#3B82F6';
        if (i === dayIndex) {
            btn.style.background = c;
            btn.style.color = 'white';
        } else {
            btn.style.background = '#F3F4F6';
            btn.style.color = '#374151';
        }
    });

    const fullUrl = buildGoogleMapsUrl(day, result);

    // Google Maps Embed สำหรับดูภายในเว็บ ใช้ /maps/embed/v1/directions
    // ต้องการ API Key สำหรับ embed - ใช้วิธี redirect ผ่าน iframe แทน
    const places = day.places || [];
    const startPoint = day.start;
    const endPoint = day.end;

    // ตรวจสอบจำนวน waypoints (Google Maps free limit = 10 waypoints)
    const warnEl = document.getElementById('gmapsWarning');
    const warnText = document.getElementById('gmapsWarningText');
    if (places.length > 10) {
        warnEl.classList.remove('hidden');
        warnText.textContent = `มีสถานที่ ${places.length} แห่ง Google Maps แสดงได้สูงสุด 10 จุดแวะ (อาจแสดงไม่ครบ)`;
    } else {
        warnEl.classList.add('hidden');
    }

    if (startPoint && endPoint) {
        renderGmapsIframe(startPoint, endPoint, places, fullUrl);
    }

    // อัปเดต "เปิดใน Google Maps" link
    document.getElementById('gmapsOpenLink').href = fullUrl;
}

function renderGmapsIframe(startPoint, endPoint, places, fullUrl) {
    const container = document.getElementById('gmapsContainer');
    const mapId = 'gmaps-route-leaflet';

    const allPoints = [startPoint, ...places, endPoint];

    // สร้าง HTML สำหรับ mini map + open button
    container.innerHTML = `
        <div class="relative rounded-xl overflow-hidden" style="height:480px;">
            <div id="${mapId}" style="height:480px;width:100%;"></div>
            <!-- Overlay button -->
            <div class="absolute bottom-4 right-4">
                <a href="${fullUrl}" target="_blank" rel="noopener noreferrer"
                   class="flex items-center gap-2 bg-white border border-gray-200 shadow-lg hover:shadow-xl px-5 py-3 rounded-xl text-sm font-bold text-gray-800 transition-all hover:bg-green-50 hover:border-green-400">
                    <img src="https://www.google.com/favicon.ico" class="w-4 h-4" alt="Google">
                    <span>เปิดเส้นทางใน Google Maps</span>
                    <i class="fas fa-external-link-alt text-green-600"></i>
                </a>
            </div>
        </div>
    `;

    // สร้าง Leaflet mini-map แสดง route
    setTimeout(() => {
        if (window._gmapsRouteMap) {
            window._gmapsRouteMap.remove();
            window._gmapsRouteMap = null;
        }

        const latlngs = allPoints.map(p => [p.lat, p.lng]);
        const routeMap = L.map(mapId, { zoomControl: true, scrollWheelZoom: true });
        window._gmapsRouteMap = routeMap;

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(routeMap);

        // วาด polyline เส้นทาง
        L.polyline(latlngs, { color: '#3B82F6', weight: 4, opacity: 0.85, dashArray: '8,4' })
            .addTo(routeMap);

        // วาง markers
        allPoints.forEach((p, i) => {
            const isStart = i === 0;
            const isEnd = i === allPoints.length - 1;
            const bgColor = isStart ? '#22C55E' : (isEnd ? '#EF4444' : '#3B82F6');
            const label = isStart ? 'S' : (isEnd ? 'E' : String(i));
            const icon = L.divIcon({
                className: '',
                html: `<div style="background:${bgColor};color:white;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:11px;border:2px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.3)">${label}</div>`,
                iconSize: [28, 28],
                iconAnchor: [14, 14],
            });
            const name = p.name || `จุด ${i}`;
            L.marker([p.lat, p.lng], { icon })
                .addTo(routeMap)
                .bindPopup(`<b>${name}</b>${isStart ? ' (จุดเริ่ม)' : isEnd ? ' (จุดสิ้นสุด)' : ` — แวะที่ ${i}`}`);
        });

        // Fit map to route
        routeMap.fitBounds(latlngs, { padding: [30, 30] });
    }, 100);
}

function renderGmapsFallback(encodedUrl) {
    const url = decodeURIComponent(encodedUrl);
    return `
        <div class="flex flex-col items-center justify-center bg-gray-50 rounded-xl" style="height:480px;">
            <div class="text-center p-8">
                <i class="fab fa-google text-green-600 text-5xl mb-4"></i>
                <h3 class="font-bold text-gray-800 text-lg mb-2">ดูเส้นทางบน Google Maps</h3>
                <p class="text-gray-500 text-sm mb-4">คลิกปุ่มด้านล่างเพื่อเปิดเส้นทางใน Google Maps</p>
                <a href="${url}" target="_blank" rel="noopener noreferrer"
                   class="inline-flex items-center gap-2 bg-green-600 hover:bg-green-700 text-white font-bold px-8 py-3 rounded-xl text-lg transition-colors shadow-lg">
                    <i class="fas fa-map-marked-alt"></i> เปิด Google Maps
                </a>
            </div>
        </div>
    `;
}

function buildGoogleMapsUrl(day, result) {
    // วันที่ 1: depot -> places -> hotel
    // วันที่ 2: hotel -> places -> depot
    const places = day.places || [];
    const startPoint = day.start;  // depot หรือ hotel (จาก backend)
    const endPoint = day.end;      // hotel หรือ depot (จาก backend)

    if (!startPoint || !endPoint) return '#';

    // origin = จุดเริ่มต้น (depot หรือ hotel)
    const origin = `${startPoint.lat},${startPoint.lng}`;
    // destination = จุดปลายทาง (hotel หรือ depot)
    const destination = `${endPoint.lat},${endPoint.lng}`;

    // waypoints = สถานที่ทุกจุดในวันนั้น (ทั้งหมด รวมถึงจุดแรกและจุดสุดท้าย)
    // Google Maps รองรับสูงสุด 10 waypoints (แบบ free) หรือ 23 waypoints (แบบ paid)
    const allWaypoints = places.map(p => `${p.lat},${p.lng}`);
    const waypoints = allWaypoints.join('|');

    let url = `https://www.google.com/maps/dir/?api=1`
        + `&origin=${encodeURIComponent(origin)}`
        + `&destination=${encodeURIComponent(destination)}`
        + `&travelmode=driving`;

    if (waypoints) {
        url += `&waypoints=${encodeURIComponent(waypoints)}`;
    }

    return url;
}

async function exportResult(format) {
    if (!currentResult) return;
    window.open(`${API}/api/v1/results/${currentResult.result_id}/export?format=${format}`);
}

async function loadResultsList() {
    const el = document.getElementById('resultsList');
    el.innerHTML = '<p class="text-gray-400 text-sm">กำลังโหลด...</p>';
    try {
        const res = await fetch(`${API}/api/v1/results`);
        const data = await res.json();
        if (!data.items || data.items.length === 0) {
            el.innerHTML = '<p class="text-gray-400 text-sm">ยังไม่มีผลลัพธ์</p>';
            return;
        }
        el.innerHTML = '';
        data.items.reverse().forEach(item => {
            el.innerHTML += `
                <div class="flex items-center justify-between p-3 border rounded-lg hover:bg-gray-50 cursor-pointer" onclick="viewResult('${item.result_id}')">
                    <div>
                        <div class="font-medium text-sm">${item.result_id}</div>
                        <div class="text-xs text-gray-400">${item.algorithm} | ${item.created_at || ''}</div>
                    </div>
                    <div class="text-right text-xs text-gray-500">
                        <div>${item.total_distance_km?.toFixed(2) || '?'} km</div>
                        <div>CO₂ ${item.total_co2_kg?.toFixed(3) || '?'} kg</div>
                    </div>
                </div>
            `;
        });
    } catch (e) {
        el.innerHTML = '<p class="text-red-500 text-sm">โหลดไม่สำเร็จ</p>';
    }
}

async function viewResult(resultId) {
    try {
        const res = await fetch(`${API}/api/v1/results/${resultId}`);
        currentResult = await res.json();
        switchTab('optimize');
        displayResult(currentResult);
    } catch (e) {
        alert('Error loading result');
    }
}

async function runCompare() {
    const algos = [...document.querySelectorAll('.cmp-algo:checked')].map(el => el.value);
    if (algos.length < 2) { alert('เลือกอย่างน้อย 2 วิธี'); return; }

    const el = document.getElementById('compareResults');
    el.innerHTML = '<div class="flex items-center gap-2"><span class="spinner"></span> กำลังเปรียบเทียบ...</div>';

    try {
        const res = await fetch(`${API}/api/v1/routes/compare?algorithms=${algos.join(',')}&trip_days=${document.getElementById('tripDays').value}&lifestyle_type=${document.getElementById('lifestyle').value}&weight_distance=${document.getElementById('wDist').value}&weight_co2=${document.getElementById('wCo2').value}&weight_rating=${document.getElementById('wRating').value}&min_places_per_day=${document.getElementById('minPlaces').value}&max_places_per_day=${document.getElementById('maxPlaces').value}`);
        const data = await res.json();
        if (!data.items) throw new Error('No results');

        let html = `
            <table class="w-full text-sm mt-4">
                <thead>
                    <tr class="border-b">
                        <th class="text-left py-2">Algorithm</th>
                        <th class="text-right py-2">Distance (km)</th>
                        <th class="text-right py-2">Time (min)</th>
                        <th class="text-right py-2">CO₂ (kg)</th>
                        <th class="text-right py-2">Compute (s)</th>
                    </tr>
                </thead>
                <tbody>
        `;
        data.items.forEach(item => {
            html += `
                <tr class="border-b hover:bg-gray-50 cursor-pointer" onclick="viewResult('${item.result_id}')">
                    <td class="py-2 font-medium">${item.algorithm.toUpperCase()}</td>
                    <td class="py-2 text-right">${item.total_distance_km.toFixed(2)}</td>
                    <td class="py-2 text-right">${item.total_time_min.toFixed(1)}</td>
                    <td class="py-2 text-right">${item.total_co2_kg.toFixed(3)}</td>
                    <td class="py-2 text-right">${item.computation_time_sec.toFixed(3)}</td>
                </tr>
            `;
        });
        html += '</tbody></table>';

        const best = data.items.reduce((a, b) => {
            const aScore = a.total_distance_km * 0.4 + a.total_time_min * 0.3 + a.total_co2_kg * 0.3;
            const bScore = b.total_distance_km * 0.4 + b.total_time_min * 0.3 + b.total_co2_kg * 0.3;
            return aScore < bScore ? a : b;
        });
        html += `<div class="mt-3 p-3 bg-green-50 rounded-lg text-sm text-green-800"><i class="fas fa-trophy mr-1"></i> วิธีที่ดีที่สุด: <b>${best.algorithm.toUpperCase()}</b></div>`;

        el.innerHTML = html;
    } catch (e) {
        el.innerHTML = `<p class="text-red-500 text-sm">Error: ${e.message}</p>`;
    }
}

async function uploadPlaces() {
    const fileInput = document.getElementById('placesFile');
    if (!fileInput.files[0]) { alert('เลือกไฟล์ก่อน'); return; }
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    const statusEl = document.getElementById('importStatus');
    statusEl.innerHTML = '<span class="spinner"></span> กำลังอัปโหลด...';
    try {
        const res = await fetch(`${API}/api/v1/files/places/import`, { method: 'POST', body: formData });
        const data = await res.json();
        statusEl.innerHTML = `<div class="text-green-600"><i class="fas fa-check-circle mr-1"></i> ${data.message} (${data.total_records} records)</div>`;
        checkDataStatus();
        markersLayer.clearLayers();
        loadAllPoints();
    } catch (e) {
        statusEl.innerHTML = `<div class="text-red-500">Error: ${e.message}</div>`;
    }
}

async function importResult() {
    const fileInput = document.getElementById('resultFile');
    if (!fileInput.files[0]) { alert('เลือกไฟล์ก่อน'); return; }
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    const statusEl = document.getElementById('importStatus');
    statusEl.innerHTML = '<span class="spinner"></span> กำลังนำเข้า...';
    try {
        const res = await fetch(`${API}/api/v1/results/import`, { method: 'POST', body: formData });
        const data = await res.json();
        statusEl.innerHTML = `<div class="text-green-600"><i class="fas fa-check-circle mr-1"></i> ${data.message} (ID: ${data.result_id})</div>`;
    } catch (e) {
        statusEl.innerHTML = `<div class="text-red-500">Error: ${e.message}</div>`;
    }
}
