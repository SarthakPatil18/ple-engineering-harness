
import ifcopenshell
from ifcopenshell import api
import sys

def create_model(output_path):
    model = ifcopenshell.file(schema="IFC4")
    project = api.run("root.create_entity", model, ifc_class="IfcProject", name="DataHall")
    site = api.run("root.create_entity", model, ifc_class="IfcSite", name="Site")
    building = api.run("root.create_entity", model, ifc_class="IfcBuilding", name="Building")
    storey = api.run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="Level 1")
    
    api.run("aggregate.assign_object", model, relating_object=project, products=[site])
    api.run("aggregate.assign_object", model, relating_object=site, products=[building])
    api.run("aggregate.assign_object", model, relating_object=building, products=[storey])
    
    # Racks
    for row in range(8):
        for col in range(16):
            rack = api.run("root.create_entity", model, ifc_class="IfcFurniture", name=f"Rack_{row}_{col}")
            api.run("aggregate.assign_object", model, relating_object=storey, products=[rack])
    
    # Routes (simple examples)
    # Telecom Tray
    tray = api.run("root.create_entity", model, ifc_class="IfcCableSegment", name="TelecomTray")
    # Busway
    busway = api.run("root.create_entity", model, ifc_class="IfcCableSegment", name="Busway")
    # Pipe
    pipe = api.run("root.create_entity", model, ifc_class="IfcPipeSegment", name="CHW_Pipe")
    
    api.run("aggregate.assign_object", model, relating_object=storey, products=[tray, busway, pipe])
    
    model.write(output_path)
    print(f"Model saved to {output_path}")

if __name__ == "__main__":
    output_path = sys.argv[1] if len(sys.argv) > 1 else "output/model.ifc"
    create_model(output_path)
