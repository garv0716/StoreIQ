const API="http://localhost:8000";
const STORE="STORE_BLR_002";

let chart=null;



async function updateMetrics(){

    const metrics=
        await fetch(
            `${API}/stores/${STORE}/metrics`
        ).then(r=>r.json());



    document.getElementById(
        "visitors"
    ).innerText=
        metrics.unique_visitors;



    document.getElementById(
        "conversion"
    ).innerText=
        (metrics.conversion_rate*100).toFixed(1)+"%";



    document.getElementById(
        "transactions"
    ).innerText=
        metrics.pos_transactions;



    document.getElementById(
        "abandonment"
    ).innerText=
        (metrics.abandonment_rate*100).toFixed(1)+"%";



    return metrics;
}





async function updateFunnel(){

    const funnel=
        await fetch(
            `${API}/stores/${STORE}/funnel`
        ).then(r=>r.json());



    document.getElementById(
        "funnel"
    ).innerHTML=
        funnel.funnel.map(s=>`

            <p>
                <b>${s.stage}</b>
                (${s.count})
            </p>

            <div
                style="
                background:#33d6a6;
                height:22px;
                border-radius:12px;
                width:${Math.max(10,s.count/3)}%;
                margin-bottom:18px;
                "
            ></div>

        `).join("");
}





async function updateAlerts(){

    const anomalies=
        await fetch(
            `${API}/stores/${STORE}/anomalies`
        ).then(r=>r.json());



    document.getElementById(
        "alerts"
    ).innerHTML=
        anomalies.anomalies
        .slice(0,5)
        .map(a=>`

        <div class="alert">

            <strong>
                ${a.anomaly_type}
            </strong>

            <br>

            Zone:
            ${a.zone_id || "General"}

            <br>

            ${a.detail}

            <br>

            <small>
                ${a.suggested_action}
            </small>

        </div>

        `).join("");
}


async function updateSecurity(){

    const security =
        await fetch(
            `${API}/security`
        ).then(r=>r.json());



    const el =
    document.getElementById(
        "securityStatus"
    );

el.innerText =
    security.backroom_status;

if(
    security.personnel_count===0
){

    el.style.color="#22c55e";

}
else{

    el.style.color="#ef4444";

}
}




async function updateChart(){

    const metrics=
        await fetch(
            `${API}/stores/${STORE}/metrics`
        ).then(r=>r.json());



    const labels=
        metrics.avg_dwell_by_zone
        .map(z=>z.zone_id);



    const values=
        metrics.avg_dwell_by_zone
        .map(z=>z.avg_dwell_sec);



    if(chart){

        chart.destroy();
    }



    chart=
        new Chart(

            document.getElementById(
                "dwellChart"
            ),

            {

                type:"bar",

                data:{

                    labels,

                    datasets:[{

                        label:"Avg Dwell",

                        data:values,

                        backgroundColor:[
                            "#22c55e",
                            "#3b82f6",
                            "#f59e0b",
                            "#ef4444",
                            "#8b5cf6",
                            "#14b8a6"
                        ]
                    }]
                }
            }
        );
}





async function askAI(){

    const input=
        document.getElementById(
            "question"
        );



    const q=input.value;



    if(!q.trim()) return;



    document.getElementById(
        "answer"
    ).innerHTML=
        "Thinking...";



    const result=
        await fetch(

            `${API}/ask`,

            {

                method:"POST",

                headers:{
                    "Content-Type":
                    "application/json"
                },

                body:JSON.stringify({
                    question:q
                })
            }

        ).then(r=>r.json());



    document.getElementById(
        "answer"
    ).innerText=
        result.answer;



    input.value="";
}





function updateClock(){

    document.getElementById(
        "clock"
    ).innerText=
        new Date()
        .toLocaleTimeString();
}





async function init(){

    await updateMetrics();
    await updateFunnel();
    await updateAlerts();
    await updateSecurity();
    await updateChart();

    updateClock();

}


init();



setInterval(()=>{

    updateMetrics();
    updateFunnel();
    updateAlerts();
    updateSecurity();
    updateChart();

    updateClock();

},5000);