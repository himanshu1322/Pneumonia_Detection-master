function toggleTheme() {
    document.documentElement.classList.toggle("dark");

    // Save user theme preference
    if (document.documentElement.classList.contains("dark")) {
        localStorage.theme = "dark";
    } else {
        localStorage.theme = "light";
    }
}

if (localStorage.theme === "dark") {
    document.documentElement.classList.add("dark");
}

// MULTI IMAGE PREVIEW
let batchImages = [];

document.getElementById("file-upload").addEventListener("change", function (e) {
    batchImages = [...e.target.files];
    showPreview();
});

function showPreview() {
    const grid = document.getElementById("preview-grid");
    grid.innerHTML = "";
    grid.classList.remove("hidden");
    document.getElementById("action-buttons").classList.remove("hidden");

    batchImages.forEach((file, index) => {
        let reader = new FileReader();
        reader.onload = function (e) {
            grid.innerHTML += `
                <div class="glass-card p-4 rounded-2xl text-center">
                    <img src="${e.target.result}" class="rounded-xl shadow-md max-h-48 mx-auto">
                    <p class="mt-2 font-semibold text-gray-700 dark:text-gray-300">Image ${index + 1}</p>
                </div>`;
        };
        reader.readAsDataURL(file);
    });
}

// CLEAR ALL
function clearBatch() {
    batchImages = [];
    document.getElementById("preview-grid").classList.add("hidden");
    document.getElementById("action-buttons").classList.add("hidden");
    document.getElementById("batch-results").classList.add("hidden");
}

// BATCH PREDICT
function predictBatch() {
    if (batchImages.length === 0) return alert("Upload some images!");

    document.getElementById("loader").classList.remove("hidden");

    let promises = batchImages.map(file => new Promise((resolve) => {
        let reader = new FileReader();
        reader.onload = function () {
            resolve(reader.result.split(",")[1]);
        };
        reader.readAsDataURL(file);
    }));

    Promise.all(promises).then(base64List => {
        fetch("/batch-predict", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ images: base64List })
        })
        .then(res => res.json())
        .then(data => {
            document.getElementById("loader").classList.add("hidden");

            const resultGrid = document.getElementById("result-grid");
            resultGrid.innerHTML = "";
            document.getElementById("batch-results").classList.remove("hidden");

            data.batch_results.forEach((item, index) => {
                resultGrid.innerHTML += `
                    <div class="glass-card p-6 rounded-3xl shadow-lg">
                        <h3 class="text-xl font-bold text-center mb-3">
                            Image ${index + 1}
                        </h3>

                        <img src="data:image/jpeg;base64,${item.image}" class="rounded-xl shadow-md mx-auto max-h-48">

                        <p class="mt-4 text-lg text-center">
                            <strong>Result:</strong> 
                            <span class="font-bold ${item.result === 'PNEUMONIA' ? 'text-red-600' : 'text-green-600'}">
                                ${item.result}
                            </span>
                        </p>

                        <p class="text-center text-gray-700 dark:text-gray-300">
                            Confidence: ${item.confidence}
                        </p>

                        <h4 class="font-semibold text-center mt-4">Heatmap:</h4>
                        <img src="data:image/jpeg;base64,${item.heatmap}" class="rounded-xl shadow-lg mx-auto mt-2">
                    </div>`;
            });
        });
    });
}
