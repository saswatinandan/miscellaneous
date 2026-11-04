
#include <TFile.h>
#include <TChain.h>
#include <TTreeReader.h>
#include <TTreeReaderArray.h>
#include <TH1F.h>
#include <TCanvas.h>
#include <TLegend.h>
#include <TStyle.h>
#include <TLorentzVector.h>
#include <TSystem.h>
#include <TSystemDirectory.h>
#include <TSystemFile.h>
#include <TList.h>
#include <TIterator.h>
#include "TLine.h"

#include <iostream>
#include <string>
#include <vector>
#include <cmath>
#include <cstdlib>

// ============================================================
// Add input ROOT files to a TChain.
//
// inputPath can be:
//   1. A single ROOT file
//   2. A directory containing ROOT files
//
// Directory search is non-recursive.
// ============================================================
//
int hnlPdgId, leptonPdgId;

template <typename T,
            typename = typename std::enable_if<std::is_arithmetic<T>::value>>
T
constrainValue(T value,
               T lowerBound,              
               T upperBound)
  {
    assert(lowerBound <= upperBound);
    value = std::max(value, lowerBound);    
    value = std::min(value, upperBound);
    return value;
}

int fillWithOverFlow(TH1 * histogram,
                 double x,
                 double evtWeight=1.,
                 double evtWeightErr=0.)
{
  if(!histogram) assert(0);
  const TAxis * const xAxis = histogram->GetXaxis();
  const int bin = constrainValue(xAxis->FindBin(x), 1, xAxis->GetNbins());
  const double binContent = histogram->GetBinContent(bin);
  const double binError   = histogram->GetBinError(bin);
  histogram->SetBinContent(bin, binContent + evtWeight);
  histogram->SetBinError(bin, std::sqrt(pow(binError,2) + 1));
  return ((bin == xAxis->GetNbins()) || (bin == 1)) ? 1 : 0;
}

template<class T>
void set_properties(T* h){

	h->Sumw2();
    h->SetDirectory(0);
}

auto createhist(const std::string& name, const std::string& title, const int& nbins, const float xlow=0.f, const float& xhigh=0.f){

	TH1F* h = new TH1F(name.c_str(), title.c_str(), nbins, xlow, xhigh);
        set_properties(h);
        return h;
}

bool addInput(TChain& chain, const std::string& inputPath)
{
    Long_t id = 0;
    Long_t size = 0;
    Long_t flags = 0;
    Long_t modtime = 0;

    if (gSystem->GetPathInfo(inputPath.c_str(),
                             &id, &size, &flags, &modtime) != 0) {
        std::cerr << "ERROR: Cannot access " << inputPath << '\n';
        return false;
    }

    // Case 1: input is a directory
        if (gSystem->OpenDirectory(inputPath.c_str()) != nullptr) {
            TSystemDirectory directory(inputPath.c_str(),
                                   inputPath.c_str());

        TList* files = directory.GetListOfFiles();

        if (!files) {
            std::cerr << "ERROR: Cannot list directory "
                      << inputPath << '\n';
            return false;
        }

        int added = 0;
        TIter next(files);
        TSystemFile* file = nullptr;

        while ((file = static_cast<TSystemFile*>(next()))) {
            const std::string name = file->GetName();

            if (file->IsDirectory())
                continue;

            if (name.size() < 5 ||
                name.substr(name.size() - 5) != ".root")
                continue;

            const std::string fullPath =
                inputPath + "/" + name;

            if (chain.Add(fullPath.c_str()) > 0) {
                std::cout << "Added: " << fullPath << '\n';
                ++added;
            }
        }

        std::cout << "Total ROOT files added from "
                  << inputPath << ": " << added << '\n';

        return added > 0;
    }

    // Case 2: input is a single file
    if (chain.Add(inputPath.c_str()) > 0) {
        std::cout << "Added: " << inputPath << '\n';
        return true;
    }

    std::cerr << "ERROR: Could not add " << inputPath << '\n';
    return false;
}

// ============================================================
// Check whether a GenPart has an HNLLepton ancestor.
//
// The search starts at the particle's mother and follows the
// mother chain until it finds the requested HNLLepton PDG ID or
// reaches a particle with no valid mother.
// ============================================================
bool hasdesiredAncestor(
    int index,
    const TTreeReaderArray<Int_t>& pdgId,
    const TTreeReaderArray<short>& mother,
    int desiredPdgId=hnlPdgId)
{
    int motherIndex = mother[index];
    int steps = 0;
    const int nParticles = static_cast<int>(pdgId.GetSize());
    int part_pdgid = abs(pdgId[index]);

    while (motherIndex >= 0 &&
           motherIndex < nParticles &&
           steps < nParticles) {

        if (std::abs(pdgId[motherIndex]) ==
            std::abs(desiredPdgId)) {
            return true;
        }
        else if (std::abs(pdgId[motherIndex]) != part_pdgid)
            return false;

        motherIndex = mother[motherIndex];
        ++steps;
    }

    return false;
}

// ============================================================
// Lepton selection: electrons, muons, and taus.
// ============================================================
bool isChargedLepton(int pdgId)
{
    const int id = std::abs(pdgId);
    return id == leptonPdgId; // || id == 11 || id == 15;
}

// ============================================================
// Histogram container for one sample.
// ============================================================
struct Histograms {
    TH1F* ptPrompt;
    TH1F* ptHNLLepton;

    TH1F* promptOSpt;
    TH1F* hnlLeptonOSpt;
    
    TH1F* promptSSpt;
    TH1F* hnlLeptonSSpt;

    TH1F* etaPrompt;
    TH1F* etaHNLLepton;

    TH1F* phiPrompt;
    TH1F* phiHNLLepton;

    TH1F *deltaR, *q1q2dldeltaR, *leptonPairMass, *q1q2dl;
    TH1F* chargeDiff;

    TH1F* hnlpt;
    TH1F* hnleta;
    TH1F* hnlmass;

    TH1F* hnlq1pt;
    TH1F* hnlq2pt;
    TH1F* hnlq1lc;
    TH1F* hnlq2lc;

    TH1F *wpt, *w_lhept, *wmass;
    explicit Histograms(const std::string& prefix)
    {
        ptPrompt = createhist((prefix + "_ptPrompt").c_str(),
            "Prompt lepton;p_{T} [GeV];Events",
            150, 5, 100);

        ptHNLLepton = createhist(
            (prefix + "_ptHNLLepton").c_str(),
            "HNLLepton-decay lepton;p_{T} [GeV];Events",
            100, 0, 50);

        promptOSpt = createhist(
            (prefix + "_promptOSpt").c_str(),
            "Prompt OS lepton;p_{T} [GeV];Events",
            200, 5, 100);

        hnlLeptonOSpt = createhist(
            (prefix + "_ptHNLLepton").c_str(),
             "HNLLepton OS;p_{T} [GeV];Events",
            100, 0, 50);

        promptSSpt = createhist(
            (prefix + "_promptSSpt").c_str(),
            "Prompt SS lepton;p_{T} [GeV];Events",
            200, 5, 100);

        wpt = createhist(
            (prefix + "_wpt").c_str(),
             "W; p_{T} [GeV];Events",
            200, 0, 100);

        w_lhept = createhist(
            (prefix + "_wpt_LHE").c_str(),
             "W; p_{T} [GeV] at LHE;Events",
            50, 0, 5);

        wmass = createhist(
            (prefix + "_wmass").c_str(),
            "W;mass [GeV];Events",
            200, 50, 100);

        hnlq1pt = createhist(
            (prefix + "_ptHNLq1").c_str(),
             "HNLq1;p_{T} [GeV];Events",
            100, 0, 50);

        hnlq2pt = createhist(
            (prefix + "_ptHNLq2").c_str(),
            "HNLq2;p_{T} [GeV];Events",
            100, 0, 50);

        hnlq1lc = createhist(
            (prefix + "_HNLq1lc").c_str(),
             "HNLq1 Last copy;;Events",
            2, 0.5, 1.5);

        hnlq2lc = createhist(
            (prefix + "_HNLq2lc").c_str(),
            "HNLq2 Last copy;;Events",
            2, 0.5, 1.5);

        hnlLeptonSSpt = createhist(
            (prefix + "_ptHNLLepton").c_str(),
             "HNLLepton SS;p_{T} [GeV];Events",
            100, 0, 50);

        etaPrompt = createhist(
            (prefix + "_etaPrompt").c_str(),
            "Prompt lepton;#eta;Events",
            50, -5, 5);

        etaHNLLepton = createhist(
            (prefix + "_etaHNLLepton").c_str(),
            "HNLLepton-decay;#eta;Events",
            50, -5, 5);

        phiPrompt = createhist(
            (prefix + "_phiPrompt").c_str(),
            "Prompt lepton;#phi;Events",
            50, -3.2, 3.2);

        phiHNLLepton = createhist(
            (prefix + "_phiHNLLepton").c_str(),
            "HNLLepton-decay lepton;#phi;Events",
            50, -3.2, 3.2);

        deltaR = createhist(
            (prefix + "_deltaR").c_str(),
            "#Delta R between leptons;#Delta R;Events",
            50, 0, 6);

        q1q2dldeltaR = createhist(
            (prefix + "_dq1q2dleltaR").c_str(),
            "#Delta R between displaced jets and lepton;#Delta R;Events",
            10, 0, 1);

        leptonPairMass = createhist(
            (prefix + "_leptonPairMass").c_str(),
            "Mass of two leptons;leptonPairMass;Events",
            50, 10, 100);

        q1q2dl = createhist(
            (prefix + "_q1q2dlMass").c_str(),
            "Mass of displaced quarks and lepton;Mass of displaced lepton and qaurks;Events",
            50, 0, 20);

        chargeDiff = createhist(
            (prefix + "_chargeDiff").c_str(),
            "#Delta charge between leptons;#Delta Charge;Events",
            3, -0.5, 2.5);

        hnlpt = createhist(
            (prefix + "_hnlpt").c_str(),
            "HNLLepton; p_{T} [GeV];Events",
            100, 5, 100);

        hnleta = createhist(
            (prefix + "_hnleta").c_str(),
            "hnl;#eta;Events",
            50, -5, 5);

        hnlmass = createhist(
            (prefix + "_hnlmass").c_str(),
            "HNLLepton; mass [GeV];Events",
            20, 0, 20);
    }

    void write()
    {
        ptPrompt->Write();
        ptHNLLepton->Write();
        etaPrompt->Write();
        etaHNLLepton->Write();
        phiPrompt->Write();
        phiHNLLepton->Write();
        deltaR->Write();
        q1q2dldeltaR->Write();
        leptonPairMass->Write();
        q1q2dl->Write();
        chargeDiff->Write();
    }
};

bool checkdisplacedIndex(
    const std::vector<int>& hnldecayindices,
    const TTreeReaderArray<Int_t>& pdgId,
    const TTreeReaderArray<short>& mother,
    int   delayedindex                    
    ) {

    int leptonindex = -1;
    for (int i=0; i<hnldecayindices.size(); i++) {
        if (abs(pdgId[hnldecayindices[i]]) == leptonPdgId) {
            leptonindex = hnldecayindices[i];
            break;
         }
    }
    while (true) {
        if (leptonindex == delayedindex) return true;
        auto motherindex = mother[delayedindex];
        if ( motherindex == leptonindex) return true;
        //std::cout << "pdgId[motherindex] " << pdgId[motherindex] << "\t" << pdgId[delayedindex] << "\t" << delayedindex << "\t" << leptonindex << std::endl;
        assert(abs(pdgId[motherindex]) == leptonPdgId);
        delayedindex = motherindex;
   }
}
std::vector<int> findhnldecay(const int& hnlindex,
    const TTreeReaderArray<Int_t>& pdgId, 
    const TTreeReaderArray<short>& mother,
    const TTreeReaderArray<UShort_t>& statusFlags,
    const int hnlPdgId = hnlPdgId ) {

    const int nParticles =
            static_cast<int>(pdgId.GetSize());
    std::vector<int> hnldecayindices;
    assert(pdgId[hnlindex] == hnlPdgId);
    
    bool leptonfound(false);
    for ( int i = 0; i < nParticles; ++i) {
        if (mother[i] == hnlindex) {
            hnldecayindices.push_back(i);
            if( abs(pdgId[i]) == leptonPdgId ) {
                assert( !leptonfound );
                leptonfound = true;
            }
        }   
    }
    assert(leptonfound);
    assert(hnldecayindices.size() != 0);
    return hnldecayindices;
}

// ============================================================
// Process all events in a sample.
//
// Selection used here:
//   - Last-copy charged leptons: statusFlags bit 13
//   - Prompt candidate: hard-process flag bit 7, no HNLLepton ancestor
//   - HNLLepton candidate: has an HNLLepton ancestor
//
// Events are retained only when exactly one prompt candidate
// and exactly one HNLLepton-descended lepton are found.
//
// IMPORTANT: This example uses unweighted event counts.
// ============================================================
void processSample(
    TChain& chain,
    Histograms& hist,
    const std::string& sampleName)
{
    std::cout << "\nProcessing sample: "
              << sampleName << '\n';

    const Long64_t nEntries = chain.GetEntries();

    std::cout << "Number of entries: "
              << nEntries << '\n';

    if (nEntries <= 0) {
        std::cerr << "WARNING: No entries found for "
                  << sampleName << '\n';
        return;
    }

    TTreeReader reader(&chain);

    TTreeReaderArray<Int_t> pdgId(
        reader, "GenPart_pdgId");

    TTreeReaderArray<Int_t> lhe_pdgId(
        reader, "LHEPart_pdgId");

    TTreeReaderArray<Int_t> lhe_status(
        reader, "LHEPart_status");

    TTreeReaderArray<Float_t> lhe_pt(
        reader, "LHEPart_pt");

    TTreeReaderArray<short> mother(
        reader, "GenPart_genPartIdxMother");

    TTreeReaderArray<UShort_t> statusFlags(
        reader, "GenPart_statusFlags");

    TTreeReaderArray<Float_t> pt(
        reader, "GenPart_pt");

    TTreeReaderArray<Float_t> eta(
        reader, "GenPart_eta");

    TTreeReaderArray<Float_t> phi(
        reader, "GenPart_phi");

    TTreeReaderArray<Float_t> mass(
        reader, "GenPart_mass");

    Long64_t eventsRead = 0;
    Long64_t eventsSelected = 0;
    Long64_t eventsNoPrompt = 0;
    Long64_t eventsNoHNLLeptonLepton = 0;
    Long64_t eventsAmbiguous = 0;

    while (reader.Next()) {
        ++eventsRead;

        std::vector<int> promptLeptons;
        std::vector<int> hnlLeptons;
        std::vector<int> hnlQuarks;

        const int nlheParticles =
            static_cast<int>(lhe_pdgId.GetSize());
        for (int i = 0; i < nlheParticles; ++i) {
            if ( (abs(lhe_pdgId[i]) == 24) && (lhe_status[i] == 2) ) fillWithOverFlow(hist.w_lhept, lhe_pt[i]);
        }
 
        const int nParticles =
            static_cast<int>(pdgId.GetSize());
        
        int hnlpartidx = -1;
        for (int i = 0; i < nParticles; ++i) {
            if ( (pdgId[i] == hnlPdgId) && ((statusFlags[i] & (1u << 13)) != 0)) { //https://github.com/cms-sw/cmssw/blob/master/PhysicsTools/NanoAOD/python/genparticles_cff.py?utm_source=chatgpt.com#L47
                assert(hnlpartidx == -1);
                hnlpartidx = i;
                fillWithOverFlow(hist.hnlpt, pt[hnlpartidx]);
                fillWithOverFlow(hist.hnleta, eta[hnlpartidx]);
                fillWithOverFlow(hist.hnlmass, mass[hnlpartidx]);
                continue;
            }
            int absPdg = std::abs(pdgId[i]);
            if ( (absPdg == 24) && (statusFlags[i] & (1u << 13)) ) {
                fillWithOverFlow(hist.wpt, pt[i]);
                fillWithOverFlow(hist.wmass, mass[i]);
                continue;
            }
            // Select quarks only (u, d, s, c, b)
            if (absPdg >= 1 && absPdg <= 5) {    
                // Check whether this quark has a same-PDG daughter
                bool hasSamePdgDaughter = false;

                for (int j = 0; j < nParticles; ++j) {

                    if (mother[j] == i && pdgId[j] == pdgId[i]) {
                         hasSamePdgDaughter = true;
                        break;
                    }
                }

                // Select terminal quark copies with an HNL ancestor
                if (!hasSamePdgDaughter &&
                      hasdesiredAncestor(i, pdgId, mother, hnlPdgId)) {
                        hnlQuarks.push_back(i);
                }
                continue;
            }
            if (!isChargedLepton(pdgId[i]))
                continue;

            // Bit 13: isLastCopy
            const bool isLastCopy =
                (statusFlags[i] & (1u << 13)) != 0;

            if (!isLastCopy)
                continue;

            if ( hasdesiredAncestor(i, pdgId, mother) ) {
                hnlLeptons.push_back(i);
            } else { //if ( hasdesiredAncestor(i, pdgId, mother, 24) ) {
                // Bit 7: isHardProcess
                /*const bool isHardProcess =
                    (statusFlags[i] & (1u << 7)) != 0;*/
                const bool fromHardProcess =
                    (statusFlags[i] & (1u << 8)) != 0;
                /*const bool isprompt = 
                        (statusFlags[i] & (1u << 0)) != 0;*/
                //std::cout << "hardprocess " << isHardProcess << "\t" << fromHardProcess << "\t" << isprompt << std::endl;
                if (fromHardProcess)
                    promptLeptons.push_back(i);
            }
        }

        if (promptLeptons.empty()) {
            ++eventsNoPrompt;
            continue;
        }

        if (hnlLeptons.empty()) {
            ++eventsNoHNLLeptonLepton;
            continue;
        }

        if (promptLeptons.size() != 1 ||
            hnlLeptons.size() != 1) {
            ++eventsAmbiguous;
            continue;
        }

        const int promptIndex = promptLeptons[0];
        const int displacedIndex = hnlLeptons[0];

        assert(hnlpartidx != -1);
        std::vector<int> hnldecayindices = findhnldecay(hnlpartidx, pdgId, mother, statusFlags);
        assert(hnldecayindices.size() == 3);
        assert(hnlQuarks.size() == 2);
        assert(checkdisplacedIndex(hnldecayindices, pdgId, mother, displacedIndex));

        int promptcharge = (pdgId[promptIndex] > 0) ? -1 : +1;
        int displacedcharge = (pdgId[displacedIndex] > 0) ? -1 : +1;

        hist.chargeDiff->Fill(abs(promptcharge + displacedcharge));
        if (    abs(promptcharge + displacedcharge) == 0 ) {
            fillWithOverFlow(hist.promptOSpt, pt[promptIndex]);
            fillWithOverFlow(hist.hnlLeptonOSpt, pt[displacedIndex]);

        }
        else {
            fillWithOverFlow(hist.promptSSpt, pt[promptIndex]);
            fillWithOverFlow(hist.hnlLeptonSSpt, pt[displacedIndex]);
        }
        // Fill kinematic histograms
        fillWithOverFlow(hist.ptPrompt, pt[promptIndex]);
        fillWithOverFlow(hist.etaPrompt, eta[promptIndex]);
        fillWithOverFlow(hist.phiPrompt, phi[promptIndex]);

        std::sort(hnlQuarks.begin(), hnlQuarks.end(),
            [&](int i, int j) {
                return pt[i] > pt[j];
        }); 
        fillWithOverFlow(hist.hnlq1pt, pt[hnlQuarks[0]]);
        fillWithOverFlow(hist.hnlq2pt, pt[hnlQuarks[1]]);
        fillWithOverFlow(hist.hnlq1lc, (statusFlags[hnlQuarks[0]] & (1u << 13)));
        fillWithOverFlow(hist.hnlq2lc, (statusFlags[hnlQuarks[1]] & (1u << 13)));

        fillWithOverFlow(hist.ptHNLLepton, pt[displacedIndex]);
        fillWithOverFlow(hist.etaHNLLepton, eta[displacedIndex]);
        fillWithOverFlow(hist.phiHNLLepton, phi[displacedIndex]);

        //std::cout << "pt[displacedIndex] " << pt[displacedIndex] << std::endl;
        assert(abs(pdgId[displacedIndex]) == abs(pdgId[promptIndex]));// == leptonPdgId);
        // Calculate Delta R between the two leptons
        TLorentzVector promptP4;
        promptP4.SetPtEtaPhiM(
            pt[promptIndex],
            eta[promptIndex],
            phi[promptIndex],
            mass[promptIndex]);

        TLorentzVector displacedP4;
        displacedP4.SetPtEtaPhiM(
            pt[displacedIndex],
            eta[displacedIndex],
            phi[displacedIndex],
            mass[displacedIndex]);

        TLorentzVector q1P4;
        q1P4.SetPtEtaPhiM(
            pt[hnlQuarks[0]],
            eta[hnlQuarks[0]],
            phi[hnlQuarks[0]],
            mass[hnlQuarks[0]]);

        TLorentzVector q2P4;
        q2P4.SetPtEtaPhiM(
            pt[hnlQuarks[1]],
            eta[hnlQuarks[1]],
            phi[hnlQuarks[1]],
            mass[hnlQuarks[1]]);

        TLorentzVector qP4 = q1P4 + q2P4;
        fillWithOverFlow(hist.leptonPairMass, (promptP4 + displacedP4).M());
        fillWithOverFlow(hist.q1q2dl, (qP4 + displacedP4).M());
        fillWithOverFlow(hist.deltaR, promptP4.DeltaR(displacedP4));
        fillWithOverFlow(hist.q1q2dldeltaR, qP4.DeltaR(displacedP4));
        ++eventsSelected;
    }

    std::cout << "\nResults for " << sampleName << ":\n"
              << "  Events read:                " << eventsRead << '\n'
              << "  Events selected:            " << eventsSelected << '\n'
              << "  Events without prompt:      " << eventsNoPrompt << '\n'
              << "  Events without HNLLepton lepton:  " << eventsNoHNLLeptonLepton << '\n'
              << "  Events with ambiguous candidates: "
              << eventsAmbiguous << '\n';
}

// ============================================================
// Normalize a histogram to unit integral.
// Empty histograms are left unchanged.
// ============================================================
void normalizeHistogram(TH1F* hist)
{
    const double integral = hist->Integral();

    if (integral > 0.0)
        hist->Scale(1.0 / integral);
}

// ============================================================
// Draw and save a normalized LO vs NLO overlay.
// ============================================================
void comparePlot(
    TH1F* loHist,
    TH1F* nloHist,
    const std::string& outputName,
    const std::string& xAxisTitle,
    const std::string& outputDir,
    const std::string& append,
    const std::string firstlabel = "LO",
    const std::string secondlabel = "NLO")
{
    TH1F* lo = static_cast<TH1F*>(
        loHist->Clone((outputName + "_LO").c_str()));

    TH1F* nlo = static_cast<TH1F*>(
        nloHist->Clone((outputName + "_NLO").c_str()));

    lo->SetDirectory(nullptr);
    nlo->SetDirectory(nullptr);

    normalizeHistogram(lo);
    normalizeHistogram(nlo);

    // Mean values
    const double meanLO  = lo->GetMean();
    const double meanNLO = nlo->GetMean();

    // Histogram styles
    lo->SetLineColor(kBlue + 1);
    lo->SetLineWidth(2);

    nlo->SetLineColor(kRed + 1);
    nlo->SetLineWidth(2);

    lo->SetTitle("");
    nlo->SetTitle("");
    lo->GetYaxis()->SetTitle("Normalized events");

    // Create the ratio histogram: NLO / LO
    TH1F* ratio = static_cast<TH1F*>(
        nlo->Clone((outputName + "_ratio").c_str()));

    ratio->SetDirectory(nullptr);
    ratio->Divide(lo);

    ratio->SetLineColor(kBlack);
    ratio->SetLineWidth(2);
    ratio->SetMarkerStyle(20);
    ratio->SetMarkerSize(0.6);

    // Canvas
    TCanvas canvas(
        ("canvas_" + outputName).c_str(),
        outputName.c_str(),
        800, 800);

    // Upper pad: LO and NLO distributions
    TPad* upperPad = new TPad("upperPad", "", 0.0, 0.30, 1.0, 1.0);
    upperPad->SetBottomMargin(0.03);
    upperPad->SetLeftMargin(0.13);
    upperPad->SetRightMargin(0.05);
    upperPad->SetTopMargin(0.08);
    upperPad->Draw();

    // Lower pad: ratio
    TPad* lowerPad = new TPad("lowerPad", "", 0.0, 0.0, 1.0, 0.30);
    lowerPad->SetTopMargin(0.03);
    lowerPad->SetBottomMargin(0.32);
    lowerPad->SetLeftMargin(0.13);
    lowerPad->SetRightMargin(0.05);
    lowerPad->Draw();

    // Draw upper plot
    upperPad->cd();

    lo->GetXaxis()->SetTitle("");
    lo->GetXaxis()->SetLabelSize(0.0);

    lo->GetYaxis()->SetTitle("Normalized events");
    lo->GetYaxis()->SetTitleSize(0.05);
    lo->GetYaxis()->SetLabelSize(0.04);
    lo->GetYaxis()->SetTitleOffset(1.15);

    lo->SetMaximum(1.20 * std::max(lo->GetMaximum(), nlo->GetMaximum()));
    lo->Draw("HIST");
    nlo->Draw("HIST SAME");

    // Display mean values in the legend
    std::ostringstream loLabel, nloLabel;
    loLabel << Form("%s (mean = ", firstlabel.c_str()) << std::fixed
            << std::setprecision(3) << meanLO << ")";
    nloLabel << Form("%s (mean = ", secondlabel.c_str()) << std::fixed
             << std::setprecision(3) << meanNLO << ")";

    TLegend legend(0.60, 0.72, 0.90, 0.90);
    legend.SetBorderSize(0);
    legend.SetFillStyle(0);
    legend.SetTextSize(0.025);
    legend.AddEntry((TObject*)nullptr, append.c_str(), "");
    legend.AddEntry(lo, loLabel.str().c_str(), "l");
    legend.AddEntry(nlo, nloLabel.str().c_str(), "l");
    legend.Draw();

    // Draw lower ratio plot
    lowerPad->cd();

    ratio->GetXaxis()->SetTitle(xAxisTitle.c_str());
    ratio->GetYaxis()->SetTitle("Ratio");

    ratio->GetXaxis()->SetTitleSize(0.12);
    ratio->GetXaxis()->SetLabelSize(0.10);
    ratio->GetXaxis()->SetTitleOffset(1.05);

    ratio->GetYaxis()->SetTitleSize(0.10);
    ratio->GetYaxis()->SetLabelSize(0.085);
    ratio->GetYaxis()->SetTitleOffset(0.55);
    ratio->GetYaxis()->SetNdivisions(505);

    ratio->SetMinimum(0.0);
    ratio->SetMaximum(2.0);

    ratio->Draw("E1");

    // Reference line at ratio = 1
    TLine* referenceLine = new TLine(
        ratio->GetXaxis()->GetXmin(), 1.0,
        ratio->GetXaxis()->GetXmax(), 1.0);

    referenceLine->SetLineColor(kRed + 1);
    referenceLine->SetLineStyle(2);
    referenceLine->SetLineWidth(2);
    referenceLine->Draw("SAME");

    // Save PNG in the requested directory
    gSystem->mkdir(outputDir.c_str(), true);

    const std::string outputPath =
        outputDir + "/" + outputName + ".png";

    canvas.SaveAs(outputPath.c_str());

    // Cleanup
    delete referenceLine;
    delete upperPad;
    delete lowerPad;

    delete ratio;
    delete lo;
    delete nlo;
}

// ============================================================
// Main analysis function
// ============================================================
void compareLO_NLO(
    const std::string& loPath,
    const std::string& nloPath,
    const std::string& outputDir
)
{
    std::string treeName = "Events";
    TChain loChain(treeName.c_str());
    TChain nloChain(treeName.c_str());

    std::cout << "Adding LO input...\n";

    if (!addInput(loChain, loPath)) {
        std::cerr << "ERROR: No LO ROOT files were added.\n";
        return;
    }

    std::cout << "\nAdding NLO input...\n";

    if (!addInput(nloChain, nloPath)) {
        std::cerr << "ERROR: No NLO ROOT files were added.\n";
        return;
    }

    Histograms loHist("LO");
    Histograms nloHist("NLO");

    // Process the samples
    processSample(
        loChain, loHist, "LO");

    processSample(
        nloChain, nloHist, "NLO");

    // Write histograms to a ROOT output file
    std::string outputFileName =
    outputDir + "/LO_vs_NLO_kinematics.root";

    std::string append = outputDir.substr(outputDir.find_last_of('/') + 1);
    TFile outputFile(outputFileName.c_str(), "RECREATE");
    if (outputFile.IsZombie()) {
        std::cerr << "ERROR: Cannot create output ROOT file.\n";
        return;
    }

    outputFile.cd();

    loHist.write();
    nloHist.write();

    outputFile.Close();

    // Produce normalized comparison plots
    gStyle->SetOptStat(0);

    comparePlot(
        loHist.ptPrompt,
        nloHist.ptPrompt,
        "compare_prompt_lepton_pt",
        "prompt lepton p_{T} [GeV]",
        outputDir,
        append);

    comparePlot(
        loHist.ptHNLLepton,
        nloHist.ptHNLLepton,
        "compare_hnl_lepton_pt",
        "HNLLepton p_{T} [GeV]",
        outputDir,
        append);

    comparePlot(
        loHist.hnlq1pt,
        nloHist.hnlq1pt,
        "compare_leading_hnlquark_pt",
        "HNL quark p_{T} [GeV]",
        outputDir,
        append);

    comparePlot(
        loHist.hnlq2pt,
        nloHist.hnlq2pt,
        "compare_subleading_hnlquark_pt",
        "HNL quark p_{T} [GeV]",
        outputDir,
        append);

    comparePlot(
        loHist.hnlq2pt,
        nloHist.hnlq2pt,
        "compare_subleading_hnlquark_pt",
        "HNL quark p_{T} [GeV]",
        outputDir,
        append);

    comparePlot(
        loHist.wpt,
        nloHist.wpt,
        "compare_w_pt",
        "W p_{T} [GeV]",
        outputDir,
        append);

    comparePlot(
        loHist.w_lhept,
        nloHist.w_lhept,
        "compare_w_pt_LHE",
        "W p_{T} [GeV] at LHE",
        outputDir,
        append);

    comparePlot(
        loHist.wmass,
        nloHist.wmass,
        "compare_w_mass",
        "w mass [GeV]",
        outputDir,
        append);

    comparePlot(
        loHist.hnlq1lc,
        nloHist.hnlq1lc,
        "compare_leading_hnlquark_LastCopy",
        "HNL quark last copy",
        outputDir,
        append);

    comparePlot(
        loHist.hnlq2lc,
        nloHist.hnlq2lc,
        "compare_subleading_hnlquark_LastCopy",
        "HNL quark last copy",
        outputDir,
        append);

    comparePlot(
        loHist.etaPrompt,
        nloHist.etaPrompt,
        "compare_prompt_lepton_eta",
        "prompt lepton #eta",
        outputDir,
        append);

    comparePlot(
        loHist.etaHNLLepton,
        nloHist.etaHNLLepton,
        "compare_hnl_lepton_eta",
        "HNLLepton #eta",
        outputDir,
        append);

    /*comparePlot(
        loHist.phiPrompt,
        nloHist.phiPrompt,
        "compare_prompt_lepton_phi",
        "prompt lepton #phi",
        outputDir,
        append);

    comparePlot(
        loHist.phiHNLLepton,
        nloHist.phiHNLLepton,
        "compare_hnl_lepton_phi",
        "HNLLepton #phi",
        outputDir,
        append);
    */
    comparePlot(
        loHist.deltaR,
        nloHist.deltaR,
        "compare_deltaR",
        "#Delta R between leptons",
        outputDir,
        append);

    comparePlot(
        loHist.q1q2dldeltaR,
        nloHist.q1q2dldeltaR,
        "compare_q1q2dldeltaR",
        "#Delta R between displaced jets and lepton",
        outputDir,
        append);

    comparePlot(
        loHist.leptonPairMass,
        nloHist.leptonPairMass,
        "compare_leptonPairMass",
        "Mass of lepton pair",
        outputDir,
        append);

    comparePlot(
        loHist.q1q2dl,
        nloHist.q1q2dl,
        "compare_q1q2dl",
        "Mass of displaced quarks and lepton",
        outputDir,
        append);

    comparePlot(
        loHist.chargeDiff,
        nloHist.chargeDiff,
        "compare_charge",
        "#Delta charge prompt vs displaced",
        outputDir,
        append);

    comparePlot(
        loHist.hnlpt,
        nloHist.hnlpt,
        "compare_hnl_pt",
        "hnl p_{T} [GeV]",
        outputDir,
        append);

    comparePlot(
        loHist.hnleta,
        nloHist.hnleta,
        "compare_hnl_eta",
        "hnl #eta",
        outputDir,
        append);

    comparePlot(
        loHist.hnlmass,
        nloHist.hnlmass,
        "compare_hnl_mass",
        "hnl mass [GeV]",
        outputDir,
        append);

    comparePlot(
        loHist.promptOSpt,
        loHist.promptSSpt,
        "compare_OS_vs_SS_prompt_lepton_pt",
        "prompt p_{T} [GeV]",
        outputDir,
        append,
        "LO OS prompt lepton",
        "LO SS prompt lepton");

    comparePlot(
        loHist.hnlLeptonOSpt,
        loHist.hnlLeptonSSpt,
        "compare_OS_vs_SS_displaced_pt",
        "displaced p_{T} [GeV]",
        outputDir,
        append,
        "LO OS displaced lepton",
        "LO SS displaced lepton");
    
    std::cout << "\nAnalysis complete.\n"
              << "ROOT output: LO_vs_NLO_kinematics.root\n"
              << "Comparison plots saved as PNG files.\n";
}

// ============================================================
// Standalone executable entry point
// Usage:
//   ./compareLO_NLO LO_path NLO_path
// ============================================================
int main(int argc, char* argv[])
{
    if (argc < 4 || argc > 5) {
        std::cerr
            << "Usage: " << argv[0]
            << " LO_path NLO_path [treeName] [hnlPdgId]\n\n"
            << "Examples:\n"
            << "  " << argv[0] << " /path/to/LO /path/to/NLO\n"
            << "  " << argv[0]
            << " LO.root NLO.root Events 9900012\n";

        return 1;
    }

    const std::string loPath = argv[1];
    const std::string nloPath = argv[2];
    const std::string outputDir = argv[3];

    leptonPdgId = (argc >= 5) ? std::atoi(argv[3]) : 13;

    hnlPdgId = (argc >= 6) ? std::atoi(argv[4]) : 9900012;

    std::cout << "comparing " << "\t" << leptonPdgId << "\t" << hnlPdgId << "\t" << argc << std::endl;
    compareLO_NLO(
        loPath, nloPath, outputDir);

    return 0;
}

