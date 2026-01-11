function showBalanceModal(userId, field) {
    // Create modal HTML
    var modalHtml = `
        <div id="balanceModal" style="
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.5);
            display: flex;
            justify-content: center;
            align-items: center;
        ">
            <div style="
                background-color: white;
                padding: 20px;
                border-radius: 5px;
                min-width: 300px;
            ">
                <h3>Modify ${field.replace('_', ' ')}</h3>
                <div style="margin: 10px 0;">
                    <label>Amount:</label>
                    <input type="number" id="balanceAmount" step="0.01" style="width: 100%;">
                </div>
                <div style="display: flex; justify-content: space-between; margin-top: 20px;">
                    <button onclick="modifyBalance('${userId}', '${field}', 'increase')" 
                            style="background-color: #79aec8; color: white; padding: 10px; border: none; border-radius: 4px; cursor: pointer;">
                        Increase
                    </button>
                    <button onclick="modifyBalance('${userId}', '${field}', 'decrease')"
                            style="background-color: #ba2121; color: white; padding: 10px; border: none; border-radius: 4px; cursor: pointer;">
                        Decrease
                    </button>
                    <button onclick="closeBalanceModal()"
                            style="background-color: #666; color: white; padding: 10px; border: none; border-radius: 4px; cursor: pointer;">
                        Cancel
                    </button>
                </div>
            </div>
        </div>
    `;

    // Add modal to body
    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

function closeBalanceModal() {
    var modal = document.getElementById('balanceModal');
    if (modal) {
        modal.remove();
    }
}

function modifyBalance(userId, field, action) {
    var amount = document.getElementById('balanceAmount').value;
    if (!amount || isNaN(amount) || amount <= 0) {
        alert('Please enter a valid amount');
        return;
    }

    // Redirect to the appropriate URL
    window.location.href = `${userId}/${action}-balance/${field}/${amount}/`;
}
