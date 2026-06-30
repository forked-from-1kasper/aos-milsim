# Copyright © 2026 rzrn

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from milsimlib.weather.google import GoogleWeather
from milsimlib.weather.openmeteo import OpenMeteo

from milsimlib.protocol import milsim_weather_provider

match milsim_weather_provider:
    case "openmeteo":
        DefaultProviderWeather = OpenMeteo
    case "google":
        DefaultProviderWeather = GoogleWeather
    case _:
        raise ValueError("Unknown weather API provider specified: {}".format(milsim_weather_provider))