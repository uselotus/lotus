import create from "zustand";

type SlideOverStoreState = {
  open: boolean;
  setOpen: () => void;
};

const useToggleSlideOver = create<SlideOverStoreState>((set) => ({
  open: false,
  setOpen: () => set((state) => ({ open: !state.open })),
}));
export default useToggleSlideOver;
