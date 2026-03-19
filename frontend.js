console.log('Script is running!');

let errands = [];
let debounceTimer;

// Set default dates (start = now, end = now + 7 days)
window.onload = function () {
  const now = new Date();
  const start = new Date(now);

  const endTime = new Date(start);
  endTime.setDate(endTime.getDate() + 7);

  document.getElementById('startDate').value = formatDateTimeLocal(start);
  document.getElementById('endDate').value = formatDateTimeLocal(endTime);
  
  // Setup autocomplete after page loads
  console.log('Setting up autocomplete...');
  setupAutocomplete('homeAddress');
  setupAutocomplete('errandAddress');
};

async function useCurrentLocation() {
  if (!navigator.geolocation) {
    alert('Geolocation is not supported by this browser.');
    return;
  }

  const homeInput = document.getElementById('homeAddress');

  navigator.geolocation.getCurrentPosition(
    async (position) => {
      const { latitude, longitude } = position.coords;
      try {
        const resp = await fetch(`http://localhost:8000/api/reverse_geocode?lat=${encodeURIComponent(latitude)}&lng=${encodeURIComponent(longitude)}`);
        if (!resp.ok) {
          throw new Error(`HTTP error! status: ${resp.status}`);
        }
        const data = await resp.json();
        if (data.address) {
          homeInput.value = data.address;
        } else {
          homeInput.value = `${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
        }
      } catch (err) {
        console.error('Reverse geocode error:', err);
        homeInput.value = `${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
      }
    },
    (error) => {
      console.error('Geolocation error:', error);
      alert('Could not get current location.');
    },
    { enableHighAccuracy: true, timeout: 10000 }
  );
}

function handleUseCurrentLocationChange(checkbox) {
  if (checkbox.checked) {
    useCurrentLocation();
  }
}

function formatDateTimeLocal(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

async function searchAddresses(query) {
  try {
    const homeInput = document.getElementById('homeAddress');
    const homeAddress = homeInput ? homeInput.value.trim() : '';

    let url = `http://localhost:8000/api/autocomplete?query=${encodeURIComponent(query)}`;
    if (homeAddress) {
      url += `&home_address=${encodeURIComponent(homeAddress)}`;
    }

    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data.suggestions || [];
  } catch (error) {
    console.error('Search error:', error);
    return [];
  }
}

function selectSuggestionFromElement(element) {
  
  const data = {
    inputId: element.dataset.inputId,
    name: element.dataset.name,
    address: element.dataset.address,
    placeId: element.dataset.placeId,
    lat: element.dataset.lat,
    lng: element.dataset.lng,
    rating: element.dataset.rating
  };
  
  const input = document.getElementById(data.inputId);
  
  if (!input) {
    console.error('❌ Input not found:', data.inputId);
    return;
  }
  
  // Fill the input
  input.value = data.address;
  
  // Store data
  input.dataset.placeName = data.name;
  input.dataset.placeId = data.placeId;
  input.dataset.lat = data.lat;
  input.dataset.lng = data.lng;
  input.dataset.fullAddress = data.address;
  
  console.log('Input dataset after storing:', input.dataset);
  
  // Auto-fill name
  if (data.inputId === 'errandAddress') {
    const nameInput = document.getElementById('errandName');
    if (nameInput && !nameInput.value) {
      nameInput.value = data.name;
    }
  }
  
  // Remove dropdown
  const dropdown = document.getElementById('suggestions-dropdown');
  if (dropdown) {
    dropdown.remove();
  }
  
  // Visual feedback
  input.classList.add('input-success');
  setTimeout(() => {
    input.classList.remove('input-success');
  }, 1500);
}

function displaySuggestions(suggestions, inputElement) {
  console.log('Displaying suggestions:', suggestions);
  
  // Remove any existing dropdown
  const existingDropdown = document.getElementById('suggestions-dropdown');
  if (existingDropdown) {
    existingDropdown.remove();
  }
  
  if (!suggestions || suggestions.length === 0) {
    console.log('No suggestions to display');
    return;
  }
  
  // Create dropdown
  const dropdown = document.createElement('div');
  dropdown.id = 'suggestions-dropdown';
  
  // Create suggestion items
  suggestions.forEach((s, index) => {
    const item = document.createElement('div');
    item.className = 'suggestion-item';
    item.dataset.index = index;
    item.dataset.name = s.name || '';
    item.dataset.address = s.address || '';
    item.dataset.placeId = s.place_id || '';
    item.dataset.lat = s.location?.lat || '';
    item.dataset.lng = s.location?.lng || '';
    item.dataset.rating = s.rating || '';
    item.dataset.inputId = inputElement.id;
    
    item.innerHTML = `
      <div class="suggestion-name">${s.name || 'Unknown'}</div>
      <div class="suggestion-address">${s.address || 'No address'}</div>
      ${s.rating ? `<div class="suggestion-rating">★ ${s.rating}</div>` : ''}
    `;
    
    item.addEventListener('click', () => {
      selectSuggestionFromElement(item);
    });
    
    dropdown.appendChild(item);
  });
  
  inputElement.parentElement.style.position = 'relative';
  inputElement.parentElement.appendChild(dropdown);
}

function hideSuggestions() {
  const dropdown = document.getElementById('suggestions-dropdown');
  if (dropdown) {
    dropdown.remove();
  }
}

function setupAutocomplete(inputId) {
  const input = document.getElementById(inputId);

  if (!input) {
    console.error(`Input element with id "${inputId}" not found`);
    return;
  }

  input.placeholder = "e.g. Whole Foods, CVS, Target";

  input.addEventListener('input', (e) => {
    const query = e.target.value;

    clearTimeout(debounceTimer);

    // Minimum 2 characters to search
    if (query.length < 2) {
      hideSuggestions();
      return;
    }

    // Wait 400ms after user stops typing
    debounceTimer = setTimeout(async () => {
      const suggestions = await searchAddresses(query);
      displaySuggestions(suggestions, input);
    }, 400);
  });

  // Handle keyboard navigation
  input.addEventListener('keydown', (e) => {
    const dropdown = document.getElementById('suggestions-dropdown');
    if (!dropdown) return;

    const items = dropdown.querySelectorAll('.suggestion-item');
    const currentActive = dropdown.querySelector('.suggestion-item--active');
    let currentIndex = -1;
    if (currentActive) {
      currentIndex = parseInt(currentActive.dataset.index);
    }

    // Arrow down
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      const nextIndex = Math.min(currentIndex + 1, items.length - 1);
      highlightItem(items, nextIndex);
    }
    // Arrow up
    else if (e.key === 'ArrowUp') {
      e.preventDefault();
      const prevIndex = Math.max(currentIndex - 1, 0);
      highlightItem(items, prevIndex);
    }
    // Enter to select
    else if (e.key === 'Enter' && currentActive) {
      e.preventDefault();
      currentActive.click();
    }
    // Escape to close
    else if (e.key === 'Escape') {
      hideSuggestions();
    }
  });
}

function highlightItem(items, index) {
  items.forEach((item, i) => {
    if (i === index) {
      item.classList.add('suggestion-item--active');
      item.scrollIntoView({ block: 'nearest' });
    } else {
      item.classList.remove('suggestion-item--active');
    }
  });
}

// Hide suggestions when clicking outside
document.addEventListener('click', (e) => {
  if (!e.target.closest('input') && !e.target.closest('#suggestions-dropdown')) {
    hideSuggestions();
  }
});

// ERRAND MANAGEMENT FUNCTIONS

function addErrand() {
  const name = document.getElementById('errandName').value.trim();
  const addressInput = document.getElementById('errandAddress');
  const address = addressInput.value.trim();
  const duration = parseInt(document.getElementById('errandDuration').value);

  if (!name || !address) {
    alert('Please fill in errand name and select a place from autocomplete');
    return;
  }

  // Get coordinates from stored data
  const lat = addressInput.dataset.lat;
  const lng = addressInput.dataset.lng;
  const placeId = addressInput.dataset.placeId;

  if (!lat || !lng) {
    alert('Please select a place from the autocomplete dropdown, not just type an address');
    return;
  }

  const errand = {
    id: Date.now(),
    name,
    address,
    place_id: placeId,
    coordinates: [parseFloat(lat), parseFloat(lng)],
    duration_minutes: duration
  };

  console.log('Adding errand:', errand);

  errands.push(errand);
  renderErrands();
  clearErrandForm();
}

function removeErrand(id) {
  errands = errands.filter(e => e.id !== id);
  renderErrands();
}

function renderErrands() {
  const container = document.getElementById('errandsList');
  
  if (errands.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
        </svg>
        <p>No errands added yet. Add your first errand above!</p>
      </div>
    `;
    return;
  }

  container.innerHTML = errands.map(errand => `
    <div class="errand-card">
      <div class="errand-header">
        <h3>${errand.name}</h3>
        <button class="btn btn-remove" onclick="removeErrand(${errand.id})">Remove</button>
      </div>
      <div class="errand-details">
        <p><strong>📍 Address:</strong> ${errand.address}</p>
        <p><strong>⏱️ Duration:</strong> ${errand.duration_minutes} minutes</p>
      </div>
    </div>
  `).join('');
}

function clearErrandForm() {
  document.getElementById('errandName').value = '';
  document.getElementById('errandAddress').value = '';
  document.getElementById('errandDuration').value = '30';
  
  // Clear stored data
  const addressInput = document.getElementById('errandAddress');
  delete addressInput.dataset.placeName;
  delete addressInput.dataset.placeId;
  delete addressInput.dataset.lat;
  delete addressInput.dataset.lng;
  delete addressInput.dataset.fullAddress;
}

// SCHEDULE GENERATION

async function generateSchedule() {
  const homeAddress = document.getElementById('homeAddress').value.trim();
  const startDate = document.getElementById('startDate').value;
  const endDate = document.getElementById('endDate').value;
  const bufferTime = parseInt(document.getElementById('bufferTime').value);

  if (!homeAddress || errands.length === 0 || !startDate || !endDate) {
    alert("Please fill out all required fields");
    return;
  }

  // Frontend guard: don't allow scheduling if start time is in the past
  const start = new Date(startDate);
  const now = new Date();
  if (start < now) {
    alert("Start time must be in the future. Please pick a time after now.");
    return;
  }

  const payload = {
    home_address: homeAddress,
    start_date: startDate,
    end_date: endDate,
    buffer_minutes: bufferTime,
    errands: errands
  };

  console.log('Sending payload:', payload);

  try {
    const response = await fetch("http://127.0.0.1:8000/api/schedule", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    
    console.log('Response status:', response.status);
    console.log('Response ok?:', response.ok);
    
    const data = await response.json();
    console.log("✅ Response data:", data);
    
    if (response.ok) {
      // Save schedule data and navigate to schedule view
      localStorage.setItem('scheduleData', JSON.stringify(data));
      window.location.href = 'schedule.html';
    } else {
      console.error('Backend error:', data);
      alert("Backend error: " + (data.detail || JSON.stringify(data)));
    }
  } catch (err) {
    console.error("❌ Full error object:", err);
    console.error("❌ Error message:", err.message);
    console.error("❌ Error stack:", err.stack);
    alert("Error: " + err.message);
  }
}


function displaySchedule(scheduled) {
  let output = '✅ Optimized Schedule Generated!\n\n';

  scheduled.forEach((errand, i) => {
    output += `${i + 1}. ${errand.name}\n`;
    output += `   📍 ${errand.address}\n`;
    output += `   🕒 ${new Date(errand.start_time).toLocaleString()} - ${new Date(errand.end_time).toLocaleTimeString()}\n`;
    output += `   🚗 Travel: ${errand.travel_time_minutes.toFixed(1)} min (${errand.distance_km.toFixed(2)} km)\n`;
    output += `   ⏱️  Duration: ${errand.duration_minutes} min\n\n`;
  });

  document.getElementById('outputSection').style.display = 'block';
  document.getElementById('scheduleOutput').textContent = output;
  document.getElementById('outputSection').scrollIntoView({ behavior: 'smooth' });
}