'use client'

import { useDashboardStore } from '@/lib/store/dashboard-store';

export default function ComponentsPanel() {
  // Get components by type using store selector
  const getComponentsByType = useDashboardStore((state) => state.getComponentsByType);
  const getValveState = useDashboardStore((state) => state.getValveState);

  const valves = getComponentsByType('valve');
  const mfcs = getComponentsByType('mfc');
  const chamberHeaters = getComponentsByType('chamber_heater');

  return (
    <div className="border border-gray-300 p-4 bg-white">
      <h2 className="text-lg font-bold mb-4">Components</h2>

      {/* Valves Section - HTML lines 222-235, 408-413 */}
      <div className="mb-6">
        <h3 className="text-md font-semibold mb-2 text-gray-700">Valves</h3>
        <div className="space-y-2">
          {valves.length === 0 ? (
            <div className="text-sm text-gray-400">No valves available</div>
          ) : (
            valves.map((valve) => {
              const value = valve.current_value ?? 0;
              const valveState = getValveState(value);

              return (
                <div
                  key={valve.id}
                  className="flex justify-between items-center border-b border-gray-200 py-2"
                >
                  <span className="text-sm font-medium">{valve.name}</span>
                  <span className={`text-sm font-semibold ${
                    valveState.state === 'OPEN' ? 'text-green-600' :
                    valveState.state === 'CLOSED' ? 'text-red-600' :
                    'text-yellow-600'
                  }`}>
                    {valveState.glyph} {valveState.state} ({value.toFixed(3)})
                  </span>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* MFCs Section - HTML lines 414-416 */}
      <div className="mb-6">
        <h3 className="text-md font-semibold mb-2 text-gray-700">MFCs</h3>
        <div className="space-y-2">
          {mfcs.length === 0 ? (
            <div className="text-sm text-gray-400">No MFCs available</div>
          ) : (
            mfcs.map((mfc) => {
              const flowRate = mfc.current_value ?? 0;

              return (
                <div
                  key={mfc.id}
                  className="flex justify-between items-center border-b border-gray-200 py-2"
                >
                  <span className="text-sm font-medium">{mfc.name}</span>
                  <span className="text-sm font-semibold text-green-600">
                    🟢 {flowRate.toFixed(1)} sccm
                  </span>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Temperature Section - HTML lines 417-421 */}
      <div className="mb-2">
        <h3 className="text-md font-semibold mb-2 text-gray-700">Temperature</h3>
        <div className="space-y-2">
          {chamberHeaters.length === 0 ? (
            <div className="text-sm text-gray-400">No heaters available</div>
          ) : (
            chamberHeaters.map((heater) => {
              const currentTemp = heater.current_value ?? 0;
              const targetTemp = heater.target_value ?? 0;

              return (
                <div
                  key={heater.id}
                  className="flex justify-between items-center border-b border-gray-200 py-2"
                >
                  <span className="text-sm font-medium">{heater.name}</span>
                  <span className="text-sm font-semibold text-blue-600">
                    🌡 {currentTemp.toFixed(0)}°C / {targetTemp.toFixed(0)}°C
                  </span>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
