import React, { useState } from "react";
import { FeatureType, CreateFeatureType } from "../../types/feature-type";
import { Button, Divider, Modal, Select, Input, message } from "antd";
import { Features } from "../../api/api";
import { UseQueryResult, useQuery } from "react-query";
import { useMutation, useQueryClient } from "react-query";

const { Option } = Select;

const FeatureForm = (props: {
  visible: boolean;
  onCancel: () => void;
  onAddFeatures: (features: FeatureType[]) => void;
}) => {
  const [newFeatures, setNewFeatures] = useState<FeatureType[]>([]);
  const [createdFeatureName, setCreatedFeatureName] = useState<string>("");
  const [createdFeatureDescription, setCreatedFeatureDescription] =
    useState<string>("");
  const queryClient = useQueryClient();
  const {
    data: features,
    isLoading,
    isError,
  }: UseQueryResult<FeatureType[]> = useQuery<FeatureType[]>(
    ["feature_list"],
    () =>
      Features.getFeatures().then((res) => {
        return res;
      })
  );

  const addExistingFeatureToList = (feature_add_list: string[]) => {
    const newFeatureList: FeatureType[] = [];
    for (let i = 0; i < feature_add_list.length; i++) {
      const feature = features?.find(
        (f) => f.feature_name === feature_add_list[i]
      );
      if (feature) {
        newFeatureList.push(feature);
      }
    }
    setNewFeatures(newFeatureList);
  };

  const addnewFeatureToList = () => {
    if (createdFeatureName !== "") {
      const featureExists = newFeatures?.find(
        (f) => f.feature_name.toLowerCase() === createdFeatureName.toLowerCase()
      );
      if (featureExists) {
        message.error("Feature already exists");
      } else {
        const newFeature: CreateFeatureType = {
          feature_name: createdFeatureName,
          feature_description: createdFeatureDescription,
        };

        Features.createFeature(newFeature).then((res) => {
          queryClient.invalidateQueries("feature_list");
          setNewFeatures([...newFeatures, res]);
        });
        setCreatedFeatureName("");
        setCreatedFeatureDescription("");
      }
    }
  };
  return (
    <Modal
      visible={props.visible}
      title={"Add Features"}
      okText="Add"
      okType="default"
      cancelText="Cancel"
      okButtonProps={{
        className: "bg-black text-white",
      }}
      onCancel={props.onCancel}
      onOk={() => {
        props.onAddFeatures(newFeatures);
      }}
    >
      <div className="grid grid-row-3">
        <div className="flex flex-col">
          <Select
            mode="multiple"
            allowClear
            placeholder="Select Feature"
            value={newFeatures.map((f) => f.feature_name)}
            loading={isLoading}
            optionLabelProp="label"
            onChange={addExistingFeatureToList}
            options={features?.map((f) => ({
              value: f.feature_name,
              label: f.feature_name,
            }))}
          />
        </div>
        <Divider />
        <div className="flex flex-col space-y-3">
          <h3>Create new feature</h3>
          <Input
            placeholder={"Feature Name"}
            value={createdFeatureName}
            onChange={(e) => setCreatedFeatureName(e.target.value)}
          ></Input>
          <Input
            placeholder={"Feature Description"}
            value={createdFeatureDescription}
            onChange={(e) => setCreatedFeatureDescription(e.target.value)}
          ></Input>

          <Button onClick={addnewFeatureToList}> Create</Button>
        </div>
      </div>
    </Modal>
  );
};

export default FeatureForm;
